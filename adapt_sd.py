import sys
from pathlib import Path
import torch
import numpy as np
from omegaconf import OmegaConf
from einops import rearrange

from torch import autocast
from contextlib import nullcontext
from math import sqrt
from adapt import ScoreAdapter

import warnings
from transformers import logging
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.set_verbosity_error()


device = torch.device("cuda")


def curr_dir():
    return Path(__file__).resolve().parent


def add_import_path(dirname):
    sys.path.append(str(
        curr_dir() / str(dirname)
    ))


def load_model_from_config(config, ckpt, verbose=False):
    from ldm.util import instantiate_from_config
    print(f"Loading model from {ckpt}")
    pl_sd = torch.load(ckpt, map_location="cpu")
    if "global_step" in pl_sd:
        print(f"Global Step: {pl_sd['global_step']}")
    if "state_dict" in pl_sd:
        pl_sd = pl_sd["state_dict"]
    #sd = pl_sd["state_dict"]
    model = instantiate_from_config(config.model)
    m, u = model.load_state_dict(pl_sd, strict=False)
    if len(m) > 0 and verbose:
        print("missing keys:")
        print(m)
    if len(u) > 0 and verbose:
        print("unexpected keys:")
        print(u)

    model.to(device)
    model.eval()
    return model


def load_sd1_model(ckpt_root):
    ckpt_fname = ckpt_root / "stable_diffusion" / "sd-v1-5.ckpt"
    cfg_fname = curr_dir() / "sd1" / "configs" / "v1-inference.yaml"
    H, W = 512, 512

    config = OmegaConf.load(str(cfg_fname))
    model = load_model_from_config(config, str(ckpt_fname))
    return model, H, W


def load_sd2_model(ckpt_root, v2_highres):
    if v2_highres:
        ckpt_fname = ckpt_root / "sd2" / "768-v-ema.ckpt"
        cfg_fname = curr_dir() / "sd2/configs/stable-diffusion/v2-inference-v.yaml"
        H, W = 768, 768
    else:
        ckpt_fname = ckpt_root / "sd2" / "512-base-ema.ckpt"
        cfg_fname = curr_dir() / "sd2/configs/stable-diffusion/v2-inference.yaml"
        H, W = 512, 512

    config = OmegaConf.load(f"{cfg_fname}")
    model = load_model_from_config(config, str(ckpt_fname))
    return model, H, W


def _sqrt(x):
    if isinstance(x, float):
        return sqrt(x)
    else:
        assert isinstance(x, torch.Tensor)
        return torch.sqrt(x)


class StableDiffusion(ScoreAdapter):
    def __init__(self, variant, v2_highres, prompt, scale, precision):
        if variant == "v1":
            add_import_path("sd1")
            self.model, H, W = load_sd1_model(self.checkpoint_root())
        elif variant == "v2":
            add_import_path("sd2")
            self.model, H, W = load_sd2_model(self.checkpoint_root(), v2_highres)
        else:
            raise ValueError(f"{variant}")

        ae_resolution_f = 8

        self._device = self.model._device

        self.prompt = prompt
        self.scale = scale
        self.precision = precision
        self.precision_scope = autocast if self.precision == "autocast" else nullcontext
        self._data_shape = (4, H // ae_resolution_f, W // ae_resolution_f)

        self.cond_func = self.model.get_learned_conditioning
        self.M = 1000
        noise_schedule = "linear"
        self.noise_schedule = noise_schedule
        self.us = self.linear_us(self.M)
        beta_start = 0.00085
        beta_end = 0.0120
        self.betas = np.linspace(beta_start**0.5, beta_end**0.5, self.M, dtype=np.float64)**2
        #betas = torch.from_numpy(betas).to(device)
        alphas = 1. - self.betas
        self.alphas_cumprod = np.cumprod(alphas, axis=0)

    def data_shape(self):
        return self._data_shape

    @property
    def sigma_max(self):
        return self.us[0]

    @property
    def sigma_min(self):
        return self.us[-1]

    @torch.no_grad()
    def denoise(self, xs, t, **model_kwargs):
        pass
        
    @torch.no_grad()
    def score(self, xs, t, **model_kwargs):
        with self.precision_scope("cuda"):
            with self.model.ema_scope():
                N = xs.shape[0]
                c = model_kwargs.pop('c')
                uc = model_kwargs.pop('uc')
                cond_t = torch.tensor([t] * N, device=self.device)
                if uc is None or self.scale == 1.:
                    output = self.model.apply_model(xs, cond_t, c)
                else:
                    x_in = torch.cat([xs] * 2)
                    t_in = torch.cat([cond_t] * 2)
                    c_in = torch.cat([uc, c])
                    e_t_uncond, e_t = self.model.apply_model(x_in, t_in, c_in).chunk(2)
                    output = e_t_uncond + self.scale * (e_t - e_t_uncond)

                if self.model.parameterization == "v":
                    output = self.model.predict_eps_from_z_and_v(xs, cond_t, output)
                else:
                    output = output

                return -output

    def cond_info(self, batch_size):
        prompts = batch_size * [self.prompt]
        return self.prompts_emb(prompts)

    @torch.no_grad()
    def prompts_emb(self, prompts):
        assert isinstance(prompts, list)
        batch_size = len(prompts)
        with self.precision_scope("cuda"):
            with self.model.ema_scope():
                cond = {}
                c = self.cond_func(prompts)
                cond['c'] = c
                uc = None
                if self.scale != 1.0:
                    uc = self.cond_func(batch_size * [""])
                cond['uc'] = uc
                return cond

    def unet_is_cond(self):
        return True

    def use_cls_guidance(self):
        return False

    def snap_t_to_nearest_tick(self, t):
        j = np.abs(t - self.us).argmin()
        return self.us[j], j

    def time_cond_vec(self, N, sigma):
        if isinstance(sigma, float):
            sigma, j = self.snap_t_to_nearest_tick(sigma)  # sigma might change due to snapping
            cond_t = (self.M - 1) - j
            cond_t = torch.tensor([cond_t] * N, device=self.device)
            return cond_t, sigma
        else:
            assert isinstance(sigma, torch.Tensor)
            sigma = sigma.reshape(-1).cpu().numpy()
            sigmas = []
            js = []
            for elem in sigma:
                _sigma, _j = self.snap_t_to_nearest_tick(elem)
                sigmas.append(_sigma)
                js.append((self.M - 1) - _j)

            cond_t = torch.tensor(js, device=self.device)
            sigmas = torch.tensor(sigmas, device=self.device, dtype=torch.float32).reshape(-1, 1, 1, 1)
            return cond_t, sigmas

    @staticmethod
    def linear_us(M=1000):
        assert M == 1000
        beta_start = 0.00085
        beta_end = 0.0120
        ## more time steps on low beta region
        betas = np.linspace(beta_start**0.5, beta_end**0.5, M, dtype=np.float64)**2
        alphas = np.cumprod(1 - betas)
        us = np.sqrt((1 - alphas) / alphas)
        us = us[::-1]
        return us

    @torch.no_grad()
    def encode(self, xs):
        model = self.model
        with self.precision_scope("cuda"):
            with self.model.ema_scope():
                zs = model.get_first_stage_encoding(
                    model.encode_first_stage(xs)
                )
        return zs

    @torch.no_grad()
    def decode(self, xs):
        with self.precision_scope("cuda"):
            with self.model.ema_scope():
                xs = self.model.decode_first_stage(xs)
                return xs


def test():
    sd = StableDiffusion("v2", True, "haha", 10.0, "autocast")
    print(sd)


if __name__ == "__main__":
    test()

