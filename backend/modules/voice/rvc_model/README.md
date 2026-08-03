# RVC Model Directory

This directory holds the trained RVC (Retrieval-based Voice Conversion) model
files used by Naira's voice pipeline.

## Expected Files

| File              | Purpose                                         |
|-------------------|------------------------------------------------|
| `naira.pth`       | RVC model weights (PyTorch checkpoint)          |
| `naira.index`     | FAISS index for voice retrieval (optional)       |

## Naming Convention

The code auto-discovers models in this directory:

- **Primary**: looks for `naira.pth` and `naira.index` by default.
- **Fallback**: if the primary names aren't found, the first `*.pth` and
  `*.index` files in this directory are used automatically.

You can drop any `.pth` + `.index` pair here and it will be picked up.

## Pipeline

1. Text → **EdgeTTS** generates base speech audio (Indian English accent).
2. Base audio → **RVC inference** transforms pitch/timbre using the `.pth`
   model + `.index` retrieval.
3. Result: Naira's trained voice output.

## System Requirements

- **Python package**: `rvc-python>=0.3.0` (`pip install rvc-python`)
- **System dependency**: `ffmpeg` must be installed and on your PATH.
  - Windows: `winget install ffmpeg` or download from https://ffmpeg.org
  - Linux: `sudo apt install ffmpeg`
  - macOS: `brew install ffmpeg`

## How to Add Your Trained Voice

1. Train your RVC model (v2 recommended) using your preferred RVC training tool.
2. Copy the resulting `.pth` file and `.index` file into this directory.
3. Optionally rename them to `naira.pth` / `naira.index` for explicit matching.
4. Restart Naira — the voice pipeline will auto-detect and use your model.
