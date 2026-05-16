# Installation Guide

## Prerequisites

- Python 3.8+
- C++ compiler (GCC or Clang)
- CMake 3.10+
- [Optional] pipx for isolated global install

## Quick Install (recommended)

The simplest way to install JANAS with all components (Python package + C++ apps):

```bash
pipx install /path/to/janas/v1.0.0
```

This installs everything in an isolated environment under `~/.local/pipx/venvs/janas/` and makes all commands globally available in `~/.local/bin/` — no environment activation needed.

If you don't have pipx:
```bash
pip install pipx
pipx ensurepath
```

## Alternative: Install in a virtual environment

If you prefer a virtual environment (e.g. for development):

```bash
git clone https://gitlab.com/topf-lab/janas.git
cd janas

python -m venv .janas_env
source .janas_env/bin/activate

pip install .
```

For development (editable install):
```bash
pip install -e .
```

## Verify the installation

```bash
janas --version
janas_utils --version
janas_app_starProcess
janas_app_meanMinMax
```

You should see version numbers and usage messages.

## Uninstall

```bash
# If installed with pipx:
pipx uninstall janas

# If installed with pip:
pip uninstall janas
```

## What gets installed

A single `pip install` (or `pipx install`) compiles and installs everything:

| Command | Description |
|---|---|
| `janas` | Main CLI (scoring, selection, classification) |
| `janas_utils` | Utility commands (masks, crops, FSC, local resolution) |
| `janas_optimizer` | Optimization and overview tools |
| `janas_session_manager` | Session creation and management |
| `janas_reconstructor` | 3D reconstruction |
| `janas_app_starProcess` | STAR file manipulation (C++) |
| `janas_app_meanMinMax` | Local resolution statistics (C++) |

No separate CMake step is needed — the C++ apps are compiled automatically during installation.
