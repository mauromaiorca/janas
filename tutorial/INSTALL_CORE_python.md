# Installation from source (development)

This guide is for contributors or users who want an editable install for development.

## Prerequisites

- Python 3.8+
- C++ compiler (GCC or Clang)
- CMake 3.10+
- git

## Clone the repository

```bash
git clone https://gitlab.com/topf-lab/janas.git
cd janas
```

To update an existing clone:
```bash
cd janas
git pull origin main
```

## Create and activate a virtual environment

```bash
python -m venv .janas_env
source .janas_env/bin/activate
pip install --upgrade pip
```

## Install in editable mode

```bash
pip install -e .
```

This compiles the C++ extension (`janas_core`) and the standalone C++ apps (`janas_app_starProcess`, `janas_app_meanMinMax`) automatically.

## Verify the installation

```bash
janas --version
janas_utils --version
janas_optimizer --version
janas_session_manager --version
janas_app_starProcess
janas_app_meanMinMax
```

## Optional: shell helper for quick activation

To make `janas_activate_environment` and `janas_deactivate_environment` available globally in your shell:

```bash
chmod +x ./src/janas/setup_environment_shell.sh
./src/janas/setup_environment_shell.sh install
source ~/.bashrc   # or source ~/.zshrc
```

Then from any directory you can simply run:
```bash
janas_activate_environment
```

## Rebuild after C++ changes

If you modify the C++ source files, rebuild with:
```bash
python setup.py build_ext --inplace
```
