# JANAS Installation Guide

## Quick install from PyPI

```bash
pip install janas
```

This downloads, compiles, and installs everything: Python modules, C++ extension, and standalone C++ apps.

### Prerequisites

- Python 3.8+
- C++ compiler (GCC on Linux, Clang on macOS)
- CMake 3.10+

On Ubuntu/WSL2:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv g++ cmake
```

On macOS (Homebrew):
```bash
brew install cmake
xcode-select --install   # provides the C++ compiler
```

### Setting up an environment

We recommend installing JANAS in an isolated environment to avoid conflicts with other packages.

**Using venv** (must activate each time you open a terminal):
```bash
python3 -m venv ~/.janas_env
source ~/.janas_env/bin/activate
pip install janas
```

To activate in future sessions:
```bash
source ~/.janas_env/bin/activate
```

To deactivate:
```bash
deactivate
```

**Using pipx** (commands always available, no activation needed):
```bash
pip install pipx
pipx ensurepath       # restart your terminal after this
pipx install janas
```

**Using conda:**
```bash
conda create -n janas python=3.11
conda activate janas
pip install janas
```

### Verify

```bash
janas --version
janas_utils --version
janas_app_starProcess
janas_app_meanMinMax
```

### Uninstall

```bash
pip uninstall janas        # if installed with pip
pipx uninstall janas       # if installed with pipx
```

### Troubleshooting

| Problem | Solution |
|---|---|
| `pip: command not found` | Use `pip3` or `python3 -m pip` |
| `externally-managed-environment` on macOS | Use a venv or pipx (see above) |
| CMake or compiler errors | Make sure `cmake` and `g++`/`clang++` are installed |
| Commands not found after pipx | Run `pipx ensurepath` and restart your terminal |

---

## Install from source

If you need the latest development version or want to modify the code, see [INSTALL_FROM_SOURCE.md](INSTALL_FROM_SOURCE.md).
