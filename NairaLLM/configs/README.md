# NairaLLM Configurations Directory

This directory stores reference configurations for training, fine-tuning, and model architectures.

## Available Configurations

| File | Purpose | Target Compute |
| :--- | :--- | :--- |
| `prototype_config.json` | Rapid CPU/NumPy prototype testing | Local CPU |
| `colab_t4_config.json` | Google Colab Free Tier Pretraining Profile | Free Tesla T4 GPU (~15 GB VRAM) |

## Source Control Rules
- All hyperparameters and architecture presets are tracked in Git.
- Trained weights (`*.pt`, `*.ckpt`, `*.npz`) are stored in Google Drive (`/content/drive/MyDrive/Naira-Training/checkpoints/`) and strictly excluded from Git.
