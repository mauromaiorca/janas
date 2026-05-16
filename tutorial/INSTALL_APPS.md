# JANAS C++ Apps

JANAS includes two compiled C++ programs that are built and installed automatically when you run `pip install janas` (or `pipx install`). No separate CMake step is required.

If you need to compile them manually (e.g. standalone use without the Python package), follow the instructions below.

## Manual compilation (standalone)

### Prerequisites

- C++ compiler (GCC or Clang): `g++ --version`
- CMake 3.10+: `cmake --version`

### Build

```bash
git clone https://gitlab.com/topf-lab/janas.git
cd janas
mkdir build && cd build
cmake ..
make
```

The executables are placed in `build/app_bin/`.

### Install to ~/.local/bin

```bash
make install
```

This installs the binaries to `~/.local/bin/` and adds it to your PATH if not already present. Reload your shell or run:

```bash
source ~/.bashrc   # or source ~/.zshrc
```

### Verify

```bash
janas_app_starProcess
janas_app_meanMinMax
```

## Usage

### janas_app_meanMinMax

Computes local resolution statistics from a local resolution map and a mask.

```bash
janas_app_meanMinMax locresMap.mrc mask.mrc
```

### janas_app_starProcess

Performs operations on STAR files: extracting parameters, exporting to half-maps, modifying metadata, and more.

```bash
janas_app_starProcess --i input.star --o output.star [options]
```

Key options:

| Option | Description |
|---|---|
| `--info` | Display general info about the STAR file |
| `--infoEuler` | Display Euler angle distribution |
| `--hm h1.mrc h2.mrc` | Export to two half-maps |
| `--csv out.csv` | Export to CSV |
| `--vem out.vem` | Export to VEM format |
| `--micrographs` | Extract unique micrograph list |
| `--checkForSimilarImages` | Compare particles and output correlation scores |

For full usage details:
```bash
janas_app_starProcess --h
```
