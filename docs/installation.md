[Repository home](../README.md) · [Docs home](index.md) · [Quick start](quick-start.md) · [CLI reference](reference/cli.md) · [Troubleshooting](troubleshooting.md)

---

# Installation

JANAS can be installed in two ways:

- **From source (recommended)** — clone the repository and install with `pip`. Gives you the latest version and full control over the source.
- **From PyPI** — quick installation of the latest released version.

## Prerequisites

- Python 3.8+
- C++ compiler (GCC on Linux, Clang on macOS)
- CMake 3.10+
- git

=== "Ubuntu / WSL2"

    ```bash
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv g++ cmake git
    ```

=== "macOS (Homebrew)"

    ```bash
    brew install cmake git
    xcode-select --install
    ```

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

For editable (development) installs and the C++ apps reference, see [Install from source](https://github.com/mauromaiorca/janas/blob/main/tutorial/INSTALL_FROM_SOURCE.md).

## Quick install from PyPI

```bash
python3 -m venv ~/.janas_env
source ~/.janas_env/bin/activate
pip install --upgrade pip
pip install janas
```

This compiles and installs the Python package, the C++ extension, and the standalone C++ apps.

### Alternative environment managers

=== "pipx"

    ```bash
    pip install pipx
    pipx ensurepath       # restart your terminal after this
    pipx install janas
    ```

    Commands are always available without activation.

=== "conda"

    ```bash
    conda create -n janas python=3.11
    conda activate janas
    pip install janas
    ```

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

## External dependencies

Some JANAS features call external programs. These must be installed separately and available on your `PATH`:

| Program | Used for | Required? |
|---------|----------|-----------|
| [RELION](https://relion.eu/) | 3D reconstruction, local resolution (when not using `--noExternalPrograms`) | Optional |
| [IMOD](https://bio3d.colorado.edu/imod/) | Volume processing | Optional |
| [pyem](https://doi.org/10.5281/zenodo.3576630) | Legacy cryoSPARC import | Optional |

With `--noExternalPrograms`, JANAS uses its own GPU/CPU reconstruction and local resolution estimation, removing the need for RELION.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `pip: command not found` | Use `pip3` or `python3 -m pip` |
| `externally-managed-environment` on macOS | Use a venv or pipx (see above) |
| CMake or compiler errors | Ensure `cmake` and `g++`/`clang++` are installed |
| Commands not found after pipx | Run `pipx ensurepath` and restart your terminal |

---

[Back to documentation index](index.md)
