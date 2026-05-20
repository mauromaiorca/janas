# Install JANAS from source

This guide covers building JANAS from the repository. Use this if you want the latest development version or plan to modify the code.

A single `pip install` from the source tree compiles and installs everything: the Python package, the C++ extension (`janas_core`), and the standalone C++ apps (`janas_app_starProcess`, `janas_app_meanMinMax`). No separate CMake step is needed.

## Prerequisites

- Python 3.8+
- C++ compiler (GCC or Clang)
- CMake 3.10+
- git

On Ubuntu/WSL2:
```bash
sudo apt install -y python3 python3-pip python3-venv g++ cmake git
```

## Clone and install

```bash
git clone https://github.com/mauromaiorca/janas.git
cd janas
python3 -m venv .janas_env
source .janas_env/bin/activate
pip install --upgrade pip
pip install .
```

For development (editable mode — changes to Python code take effect immediately):
```bash
pip install -e .
```

To update an existing clone:
```bash
cd janas
git pull origin main
pip install .
```

## Verify

```bash
janas --version
janas_utils --version
janas_app_starProcess
janas_app_meanMinMax
```

## Rebuild after C++ changes

If you modify files in `src/src_cpp/`, rebuild with:
```bash
python setup.py build_ext --inplace
```

## Optional: shell activation shortcut

To avoid typing `source .janas_env/bin/activate` every time:

```bash
chmod +x ./src/janas/setup_environment_shell.sh
./src/janas/setup_environment_shell.sh install
source ~/.bashrc   # or source ~/.zshrc
```

Then from any directory, just run:
```bash
janas_activate_environment
```

## What gets installed

| Command | Description |
|---|---|
| `janas` | Main CLI: particle scoring, selection, classification |
| `janas_utils` | Utilities: masks, image crops, FSC, local resolution, half-map randomization |
| `janas_optimizer` | Optimization and overview analysis |
| `janas_session_manager` | Create and manage selection/classification sessions |
| `janas_reconstructor` | 3D reconstruction from scored particles |
| `janas_app_starProcess` | STAR file manipulation (C++) |
| `janas_app_meanMinMax` | Local resolution statistics (C++) |

## C++ apps usage reference

### janas_app_starProcess

Manipulates STAR files: inspect metadata, extract subsets, export formats, compare particles.

```bash
janas_app_starProcess --i input.star --o output.star [options]
```

| Option | Description |
|---|---|
| `--info` | Display particle count, labels, and subset distribution |
| `--infoEuler` | Display Euler angle statistics |
| `--hm h1.mrc h2.mrc [tag]` | Export particles to two half-map stacks |
| `--csv output.csv` | Export to CSV format |
| `--vem output.vem` | Export to VEM format |
| `--micrographs [depth]` | Extract unique micrograph list |
| `--checkForSimilarImages` | Find particles with similar coordinates |
| `--invertTagName tag1 tag2` | Swap two column values |
| `--backupImageNameTag [tag]` | Back up \_rlnImageName to a custom tag |

Run `janas_app_starProcess --h` for the full list.

Examples:
```bash
# Inspect a STAR file
janas_app_starProcess --i particles.star --info

# Export to CSV
janas_app_starProcess --i particles.star --csv particles.csv

# Split into half-map stacks
janas_app_starProcess --i particles.star --o out.star --hm half1.mrc half2.mrc
```

### janas_app_meanMinMax

Computes statistics (mean, min, max) from a local resolution map within a masked region.

```bash
janas_app_meanMinMax locresMap.mrc mask.mrc
```

## Manual C++ compilation (optional)

If you only need the C++ apps without the Python package:

```bash
git clone https://github.com/mauromaiorca/janas.git
cd janas
mkdir build && cd build
cmake ..
make
make install   # installs to ~/.local/bin
```
