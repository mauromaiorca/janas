# Installation

## Prerequisites

- Python 3.8+
- C++ compiler (GCC on Linux, Clang on macOS)
- CMake 3.10+

=== "Ubuntu / WSL2"

    ```bash
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv g++ cmake
    ```

=== "macOS (Homebrew)"

    ```bash
    brew install cmake
    xcode-select --install
    ```

## Install from PyPI

```bash
pip install janas
```

This compiles and installs the Python package, the C++ extension, and the standalone C++ apps.

## Environment setup

We recommend installing JANAS in an isolated environment.

=== "venv"

    ```bash
    python3 -m venv ~/.janas_env
    source ~/.janas_env/bin/activate
    pip install janas
    ```

    Activate in future sessions:

    ```bash
    source ~/.janas_env/bin/activate
    ```

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

## Install from source

If you need the latest development version or plan to modify the code:

```bash
git clone https://github.com/mauromaiorca/janas.git
cd janas
python3 -m venv .janas_env
source .janas_env/bin/activate
pip install .
```

For development (editable mode):

```bash
pip install -e .
```

See [Install from source](https://github.com/mauromaiorca/janas/blob/main/tutorial/INSTALL_FROM_SOURCE.md) for the full reference, including manual C++ compilation and shell shortcuts.

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
