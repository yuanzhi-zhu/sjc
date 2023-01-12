# Update:

Nocicing that most of the pre-trained diffusion models are VP-SDE diffusion models like DDPM, and the relationship between score and noise prediction 
$$\boldsymbol{s}_\theta(\boldsymbol{x}_t,t)&\approx&\nabla_{\boldsymbol{x}_t} \log p(\boldsymbol{x}_t|\boldsymbol{x}_0) = -\frac{\boldsymbol{x}_t - \bar{\alpha}_t\boldsymbol{x}_0}{{1-\bar{\alpha}_t}} = -\frac{\boldsymbol{\varepsilon}}{\sqrt{1-\bar{\alpha}_t}} \approx -\frac{\boldsymbol{\varepsilon}_\theta(\boldsymbol{x}_t,t)}{\sqrt{1-\bar{\alpha}_t}}$$, 
there is no need to inteprete the score from a denoiser point of view.

# Score Jacobian Chaining: Lifting Pretrained 2D Diffusion Models for 3D Generation

[Haochen Wang*](https://whc.is/),
[Xiaodan Du*](https://xiaodan.io),
[Jiahao Li*](https://www.linkedin.com/in/jiahaoli95/),
[Raymond A. Yeh&dagger;](https://raymond-yeh.com),
[Greg Shakhnarovich](https://home.ttic.edu/~gregory/)
(* indicates equal contribution)

TTI-Chicago, &dagger;Purdue University

Abstract: *A diffusion model learns to predict a vector field of gradients. We propose to apply chain rule on the learned gradients, and back-propagate the score of a diffusion model through the Jacobian of a differentiable renderer, which we instantiate to be a voxel radiance field. This setup aggregates 2D scores at multiple camera viewpoints into a 3D score, and repurposes a pretrained 2D model for 3D data generation. We identify a technical challenge of distribution mismatch that arises in this application, and propose a novel estimation mechanism to resolve it. We run our algorithm on several off-the-shelf diffusion image generative models, including the recently released Stable Diffusion trained on the large-scale LAION dataset.*


<a href="https://arxiv.org/abs/2212.00774"><img src="https://img.shields.io/badge/arXiv-2212.00774-b31b1b.svg" height=22.5></a>
<a href="https://pals.ttic.edu/p/score-jacobian-chaining"><img src="https://img.shields.io/website?down_color=lightgrey&down_message=offline&label=Project%20Page&up_color=lightgreen&up_message=online&url=https%3A%2F%2Fpals.ttic.edu%2Fp%2Fscore-jacobian-chaining" height=22.5></a>
<a href="https://colab.research.google.com/drive/1zixo66UYGl70VOPy053o7IV_YkQt5lCZ?usp=sharing"><img src="https://colab.research.google.com/assets/colab-badge.svg" height=22.5></a>
<a href="https://huggingface.co/spaces/MirageML/sjc"><img src="https://img.shields.io/badge/🤗-Huggingface%20Space-cyan.svg" height=22.5></a>

<!-- [ [arxiv](https://arxiv.org/abs/2212.00774) | [project page](https://pals.ttic.edu/p/score-jacobian-chaining) | [colab](https://colab.research.google.com/drive/1zixo66UYGl70VOPy053o7IV_YkQt5lCZ?usp=sharing ) ] -->

Many thanks to [dvschultz](https://github.com/dvschultz) for the colab, and [AmanKishore](https://github.com/AmanKishore) for the hugging face demo. 


<img src="https://user-images.githubusercontent.com/17956191/206826892-d056ad70-b586-4b39-a4d3-6f91c814aa10.gif" width="500px"/>


## Updates
- We have added subpixel rendering script for final high quality vis. The jittery videos you might have seen should be significantly better now. Please run `python /path/to/sjc/highres_final_vis.py` in the exp folder after the training is complete. There are a few toggles in the script you can play with, but the default is ok. It takes about 5 minutes / 11GB on an A5000, and the extra time is mainly due to SD Decoder. 
- If you are running SJC with a DreamBooth fine-tuned model: the model's output distribution is already significantly narrowed. It might help to use a lower guidance scale `--sd.scale 50.0` for example. Intense mode-seeking is one cause for multi-face problem. We have internally tried DreamBooth with view-dependent prompt fine-tuning. But by and large DreamBooth integration is not ready. 


## TODOs
- [ ] make seeds configurable. So far all seeds are hardcoded to 0. 
- [ ] add script to reproduce 2D experiments in Fig 4. The Fig might need change once it's tied to seeds. Note that for a simple aligned domain like faces, simple scheduling like using a single σ=1.5 could already generate some nice images. But not so for bedrooms; it's too diverse and annealing seems still needed.
- [ ] main paper figures did not use subpix rendering; appendix figures did. Replace the main paper figures to make them consistent.

## License
Since we use Stable Diffusion, we are releasing under their OpenRAIL license. Otherwise we do not
identify any components or upstream code that carry restrictive licensing requirements.

## Structure
In addition to SJC, the repo also contains an implementation of [Karras sampler](https://arxiv.org/abs/2206.00364),
and a customized, simple voxel nerf. We provide the abstract parent class based on Karras et. al. and include
a few types of diffusion model here. See adapt.py.

## Installation

Install Pytorch according to your CUDA version, for example:
```bash
pip3 install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu116
```

Install other dependencies by `pip install -r requirements.txt`.

Install `taming-transformers` manually
```bash
git clone --depth 1 git@github.com:CompVis/taming-transformers.git && pip install -e taming-transformers
```

## Downloading checkpoints
We have bundled a minimal set of things you need to download (SD v1.5 ckpt, gddpm ckpt for LSUN and FFHQ)
in a tar file, made available at our download server [here](https://dl.ttic.edu/pals/sjc/release.tar).
It is a single file of 12GB, and you can use wget or curl.

Remember to __update__ `env.json` to point at the new checkpoint root where you have uncompressed the files.

## Usage
Make a new directory to run experiments (the script generates many logging files. Do not run at the root of the code repo, else risk contamination.)
```bash
mkdir exp
cd exp
```
Run the following command to generate a new 3D asset. It takes about 25 minutes / 10GB GPU mem on a single A5000 GPU for 10000 steps of optimization.
```bash
python /path/to/sjc/run_sjc.py \
--sd.prompt "A zoomed out high quality photo of Temple of Heaven" \
--n_steps 10000 \
--lr 0.05 \
--sd.scale 100.0 \
--emptiness_weight 10000 \
--emptiness_step 0.5 \
--emptiness_multiplier 20.0 \
--depth_weight 0 \
--var_red False
```
`sd.prompt` is the prompt to the stable diffusion model

`n_steps` is the number of gradient steps

`lr` is the base learning rate of the optimizer

`sd.scale` is the guidance scale for stable diffusion

`emptiness_weight` is the weighting factor of the emptiness loss

`emptiness_step` indicates after `emptiness_step * n_steps` update steps, the `emptiness_weight` is multiplied by `emptiness_multiplier`.

`emptiness_multipler` see above

`depth_weight` the weighting factor of the center depth loss

`var_red` whether to use Eq. 16 vs Eq. 15. For some prompts such as Obama we actually see better results with Eq. 15.

Visualization results are stored in the current directory. In directories named `test_*` there are images (under `view`) and videos (under `view_seq`) rendered at different iterations.


## To Reproduce the Results in the Paper
First create a clean directory for your experiment, then run one of the following scripts from that folder:
### Trump
```
python /path/to/sjc/run_sjc.py --sd.prompt "Trump figure" --n_steps 30000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0
```
### Obama
```
python /path/to/sjc/run_sjc.py --sd.prompt "Obama figure" --n_steps 30000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0 --var_red False
```
### Biden
```
python /path/to/sjc/run_sjc.py --sd.prompt "Biden figure" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0
```
### Temple of Heaven
```
python /path/to/sjc/run_sjc.py --sd.prompt "A zoomed out high quality photo of Temple of Heaven" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0
```
### Burger
```
python /path/to/sjc/run_sjc.py --sd.prompt "A high quality photo of a delicious burger" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0
```
### Icecream
```
python /path/to/sjc/run_sjc.py --sd.prompt "A high quality photo of a chocolate icecream cone" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 10

```
### Ficus
```
python /path/to/sjc/run_sjc.py --sd.prompt "A ficus planted in a pot" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 100
```
### Castle
```
python /path/to/sjc/run_sjc.py --sd.prompt "A zoomed out photo a small castle" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 50
```
### Sydney Opera House
```
python /path/to/sjc/run_sjc.py --sd.prompt "A zoomed out high quality photo of Sydney Opera House" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0
```
### Rose
```
python /path/to/sjc/run_sjc.py --sd.prompt "a DSLR photo of a rose" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 50
```
### School Bus
```
python /path/to/sjc/run_sjc.py --sd.prompt "A high quality photo of a yellow school bus" --n_steps 30000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0 --var_red False
```
### Rocket
```
python /path/to/sjc/run_sjc.py --sd.prompt "A wide angle zoomed out photo of Saturn V rocket from distance" --n_steps 30000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0  --var_red False
```
### French Fries
```
python /path/to/sjc/run_sjc.py --sd.prompt "A high quality photo of french fries from McDonald's" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 10
```
### Motorcycle
```
python /path/to/sjc/run_sjc.py --sd.prompt "A high quality photo of a toy motorcycle" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0
```
### Car
```
python /path/to/sjc/run_sjc.py --sd.prompt "A high quality photo of a classic silver muscle car" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0
```
### Tank
```
python /path/to/sjc/run_sjc.py --sd.prompt "A product photo of a toy tank" --n_steps 20000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0
```
### Chair
```
python /path/to/sjc/run_sjc.py --sd.prompt "A high quality photo of a Victorian style wooden chair with velvet upholstery" --n_steps 50000 --lr 0.01 --sd.scale 100.0 --emptiness_weight 7000
```
### Duck
```
python /path/to/sjc/run_sjc.py --sd.prompt "a DSLR photo of a yellow duck" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 10
```
### Horse
```
python /path/to/sjc/run_sjc.py --sd.prompt "A photo of a horse walking" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0
```
### Giraffe
```
python /path/to/sjc/run_sjc.py --sd.prompt "A wide angle zoomed out photo of a giraffe" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 50
```
### Zebra
```
python /path/to/sjc/run_sjc.py --sd.prompt "A photo of a zebra walking" --n_steps 10000 --lr 0.02 --sd.scale 100.0 --emptiness_weight 30000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0 --var_red False
```
### Printer
```
python /path/to/sjc/run_sjc.py --sd.prompt "A product photo of a Canon home printer" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0 --var_red False
```
### Zelda Link
```
python /path/to/sjc/run_sjc.py --sd.prompt "Zelda Link" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0 --var_red False
```
### Pig
```
python /path/to/sjc/run_sjc.py --sd.prompt "A pig" --n_steps 10000 --lr 0.05 --sd.scale 100.0 --emptiness_weight 10000 --emptiness_step 0.5 --emptiness_multiplier 20.0 --depth_weight 0
```


## To Test the Voxel NeRF
```
python /path/to/sjc/run_nerf.py
```
Our bundle contains a tar ball for the lego bulldozer dataset. Untar it and it will work.

## To Sample 2D images with the Karras Sampler
```
python /path/to/sjc/run_img_sampling.py
```
Use help -h to see the options available. Will expand the details later.


## Bib
```
@article{sjc,
      title={Score Jacobian Chaining: Lifting Pretrained 2D Diffusion Models for 3D Generation},
      author={Wang, Haochen and Du, Xiaodan and Li, Jiahao and Yeh, Raymond A. and Shakhnarovich, Greg},
      journal={arXiv preprint arXiv:2212.00774},
      year={2022},
}
```
