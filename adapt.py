from pathlib import Path
import json
from math import sqrt
import numpy as np
import torch
from abc import ABCMeta, abstractmethod


class ScoreAdapter(metaclass=ABCMeta):

    @abstractmethod
    def denoise(self, xs, sigma, **kwargs):
        pass

    def score(self, xs, sigma, **kwargs):
        Ds = self.denoise(xs, sigma, **kwargs)
        grad_log_p_t = (Ds - xs) / (sigma ** 2)
        return grad_log_p_t

    @abstractmethod
    def data_shape(self):
        return (3, 256, 256)  # for example

    def samps_centered(self):
        # if centered, samples expected to be in range [-1, 1], else [0, 1]
        return True

    @property
    @abstractmethod
    def sigma_max(self):
        pass

    @property
    @abstractmethod
    def sigma_min(self):
        pass

    def cond_info(self, batch_size):
        return {}

    @abstractmethod
    def unet_is_cond(self):
        return False

    @abstractmethod
    def use_cls_guidance(self):
        return False  # most models do not use cls guidance

    def classifier_grad(self, xs, sigma, ys):
        raise NotImplementedError()

    @abstractmethod
    def snap_t_to_nearest_tick(self, t):
        # need to confirm for each model; continuous time model doesn't need this
        return t, None

    @property
    def device(self):
        return self._device

    def checkpoint_root(self):
        """the path at which the pretrained checkpoints are stored"""
        with Path(__file__).resolve().with_name("env.json").open("r") as f:
            root = json.load(f)['data_root']
            root = Path(root) / "diffusion_ckpts"
        return root


def karras_t_schedule(rho=7, N=10, sigma_max=80, sigma_min=0.002):
    ts = []
    for i in range(N):

        t = (
            sigma_max ** (1 / rho) + (i / (N - 1)) * (sigma_min ** (1 / rho) - sigma_max ** (1 / rho))
        ) ** rho
        ts.append(t)
    return ts


def power_schedule(sigma_max, sigma_min, num_stages):
    sigmas = np.exp(np.linspace(np.log(sigma_max), np.log(sigma_min), num_stages))
    return sigmas


class Karras():

    @classmethod
    @torch.no_grad()
    def inference(
        cls, model, batch_size, num_t, *,
        sigma_max=80, cls_scaling=1,
        init_xs=None, heun=True,
        langevin=False,
        S_churn=80, S_min=0.05, S_max=50, S_noise=1.003,
    ):
        sigma_max = min(sigma_max, model.sigma_max)
        sigma_min = model.sigma_min
        ts = karras_t_schedule(rho=7, N=num_t, sigma_max=sigma_max, sigma_min=sigma_min)
        assert len(ts) == num_t
        ts = [model.snap_t_to_nearest_tick(t)[0] for t in ts]
        ts.append(0)  # 0 is the destination
        sigma_max = ts[0]

        cond_inputs = model.cond_info(batch_size)

        def compute_step(xs, sigma):
            grad_log_p_t = model.score(
                xs, sigma, **(cond_inputs if model.unet_is_cond() else {})
            )
            if model.use_cls_guidance():
                grad_cls = model.classifier_grad(xs, sigma, cond_inputs["y"])
                grad_cls = grad_cls * cls_scaling
                grad_log_p_t += grad_cls
            d_i = -1 * sigma * grad_log_p_t
            return d_i

        if init_xs is not None:
            xs = init_xs.to(model.device)
        else:
            xs = sigma_max * torch.randn(
                batch_size, *model.data_shape(), device=model.device
            )

        yield xs

        for i in range(num_t):
            t_i = ts[i]

            if langevin and (S_min < t_i and t_i < S_max):
                xs, t_i = cls.noise_backward_in_time(
                    model, xs, t_i, S_noise, S_churn / num_t
                )

            delta_t = ts[i+1] - t_i

            d_1 = compute_step(xs, sigma=t_i)
            xs_1 = xs + delta_t * d_1

            # Heun's 2nd order method; don't apply on the last step
            if (not heun) or (ts[i+1] == 0):
                xs = xs_1
            else:
                d_2 = compute_step(xs_1, sigma=ts[i+1])
                xs = xs + delta_t * (d_1 + d_2) / 2

            yield xs

    @staticmethod
    def noise_backward_in_time(model, xs, t_i, S_noise, S_churn_i):
        n = S_noise * torch.randn_like(xs)
        gamma_i = min(sqrt(2)-1, S_churn_i)
        t_i_hat = t_i * (1 + gamma_i)
        t_i_hat = model.snap_t_to_nearest_tick(t_i_hat)[0]
        xs = xs + n * sqrt(t_i_hat ** 2 - t_i ** 2)
        return xs, t_i_hat


def test():
    pass


if __name__ == "__main__":
    test()

