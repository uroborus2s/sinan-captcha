# sinan-captcha

Python CLI and training/data-engineering package for the `sinan-captcha` monorepo.

This package provides the `sinan` command and the top-level `src/` feature packages used for:

- materials preparation
- dataset validation
- training and evaluation flows
- autonomous training control
- local solver bundle packaging

Dependency boundary:

- base install: lightweight CLI and packaging entrypoints
- `sinan-captcha[train]`: shared training/runtime dependencies without pinning a PyTorch backend
- dedicated training root: installs `sinan-captcha[train]` plus machine-specific `torch/torchvision/torchaudio`
