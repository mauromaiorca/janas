# JANAS Installation Guide

JANAS can be installed in two ways:

- **From source (recommended)** — clone the repository and install with `pip`. Gives you the latest version and full control over the source.
- **From PyPI** — quick installation of the latest released version.

## Prerequisites

- Python 3.8+
- C++ compiler (GCC on Linux, Clang on macOS)
- CMake 3.10+
- git

On Ubuntu/WSL2:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv g++ cmake git
```

On macOS (Homebrew):

```bash
brew install cmake git
xcode-select --install   # provides the C++ compiler
```

---

## Recommended: full installation from source

This sequence creates a fresh virtual environment and installs JANAS in one go:

```bash
# 1. Create a working directory
mkdir -p ~/janas_install
cd ~/janas_install

# 2. Create and activate a new virtual environment
python3 -m venv ~/.janas_env
source ~/.janas_env/bin/activate

# 3. Upgrade pip
pip install --upgrade pip

# 4. Clone the repository
git clone https://github.com/mauromaiorca/janas.git
cd janas

# 5. Install JANAS (Python + C++ extension + C++ apps)
pip install .

# 6. Verify
janas --version
janas_utils --version
janas_app_starProcess
janas_app_meanMinMax
```

In future sessions, activate the environment with:

```bash
source ~/.janas_env/bin/activate
```

To update later:

```bash
source ~/.janas_env/bin/activate
cd ~/janas_install/janas
git pull origin main
pip install --upgrade .
```

For development mode (editable, Python changes take effect immediately) and the C++ apps reference, see [INSTALL_FROM_SOURCE.md](INSTALL_FROM_SOURCE.md).

---

## Quick install from PyPI

```bash
python3 -m venv ~/.janas_env
source ~/.janas_env/bin/activate
pip install --upgrade pip
pip install janas
```

This downloads, compiles, and installs everything: Python modules, C++ extension, and standalone C++ apps.

### Alternative environment managers

**pipx** (commands always available, no activation needed):

```bash
pip install pipx
pipx ensurepath       # restart your terminal after this
pipx install janas
```

**conda:**

```bash
conda create -n janas python=3.11
conda activate janas
pip install janas
```

---

## Verify

```bash
janas --version
janas_utils --version
janas_app_starProcess
janas_app_meanMinMax
```

## Uninstall

```bash
pip uninstall janas        # if installed with pip
pipx uninstall janas       # if installed with pipx
```

To also remove the virtual environment:

```bash
deactivate
rm -rf ~/.janas_env
```

## Troubleshooting

| Problem | Solution |
|---|---|
| `pip: command not found` | Use `pip3` or `python3 -m pip` |
| `externally-managed-environment` on macOS | Use a venv or pipx (see above) |
| CMake or compiler errors | Make sure `cmake` and `g++`/`clang++` are installed |
| Commands not found after pipx | Run `pipx ensurepath` and restart your terminal |
