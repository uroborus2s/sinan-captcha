Write-Host "Checking NVIDIA driver..."
nvidia-smi

Write-Host "Checking Python CUDA visibility..."
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
