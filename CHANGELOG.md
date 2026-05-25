# Changelog

## 1.0.8

- Add `utils.backmap_stars()` — the inverse companion of `create_stack_from_star`. Restores the original source `_rlnImageName` in a downstream STAR file by joining against the stack-generation STAR (which carries `_janas_source_rlnImageName`), preserving all refined metadata. Optionally writes `_janas_stack_rlnImageName` as an audit column so the rewrite is reversible.
- Expose it as `janas_utils backmap_stars --processed P.star --mapping S.star --output O.star` (`--no-strict`, `--stack-reference-tag ""`, `--section-name` available).
- Add `tests/test_backmap_stars.py` covering: row-order-independent mapping, metadata preservation, audit column, strict vs non-strict missing keys, missing provenance column in the mapping STAR, conflicting duplicate keys, tolerated consistent duplicate keys.

## 1.0.7

- Declare `cmake>=3.10` as a build-system requirement in `pyproject.toml`. Some Python environments (notably colabfold's bundled conda) ship a Python wrapper at `<env>/bin/cmake` that depends on the `cmake` Python package without installing it, breaking the build with `ModuleNotFoundError: No module named 'cmake'`. With this change, pip's default build isolation will install a working CMake before invoking our build.

## 1.0.6

- Add a `gpu` extra so `pip install 'janas[gpu]'` pulls a generic PyTorch wheel. Users who need a specific CUDA build should still install torch manually via `--index-url`.
- `janas_reconstructor --gpu` now fails fast with a clear error message and install hints (including the `--index-url cu128 / cu121 / cu118` examples and `pip install 'janas[gpu]'`) when PyTorch is not available, instead of crashing inside torch-using code paths.

## 1.0.5

- Revert the default CTF application mode for particle scoring from `modulate` back to `phaseflip`. This restores the manuscript-described behaviour for `janas scoreParticles`, `janas_session_manager new_select_session`, and `janas_session_manager classification_session`. `modulate` and `wiener` remain available via `--ctf-mode`.

## 1.0.4

- Add `--noRecs` option to `janas_session_manager classification_session`. When set, the generated run script skips all per-class reconstructions and only performs scoring and class assignment. Per-class STAR files are still written, so the user can reconstruct each class independently with their preferred software (RELION, cryoSPARC, `janas_reconstructor`, etc.).

## 1.0.3

- Change the default CTF application mode for particle scoring from `phaseflip` to `modulate` (multiply by the full CTF). This applies to `janas scoreParticles`, `janas_session_manager classification_session`, and `janas_session_manager new_select_session`.
- Fix `new_select_session --ctf-mode`: align choices with `janas scoreParticles` (`modulate`, `phaseflip`, `wiener`) — previous choices (`none`, `image`, `phaseflip`, `ref`) did not match the scoring backend.
- The selected CTF mode is now actually propagated to all `janas scoreParticles` invocations in the generated selection run script.

## 1.0.2

- Add `--ctf-mode` option to `janas_session_manager classification_session`. Choices: `modulate`, `phaseflip` (default), `wiener`. The flag is propagated to the `janas scoreParticles` calls in the generated run script, so the chosen CTF handling is applied during class scoring.

## 1.0.1

- Wrap `os.chmod` calls in `try / except PermissionError` for Windows compatibility (some filesystems do not permit `chmod`).

## 1.0.0

- First public release on PyPI.
- Integrated C++ app compilation into `pip install` (no separate CMake step).
- Added `janas_utils csparc2star-stack` for direct cryoSPARC particle import.
- Added `janas_utils update_from_csparc` for updating STAR metadata from cryoSPARC jobs.
- Added GPU-accelerated 3D reconstruction (`janas_reconstructor`).
- Added `--noExternalPrograms` mode for self-contained operation without RELION.
- Renamed project from emprove to JANAS. Backward compatibility with `_emprove_` STAR tags is preserved.

## 0.1.3.x

- Development releases under the name emprove.
- Iterative particle selection and 3D class reassignment workflows.
- CryoSPARC integration for local NU-refinement.
- Local resolution estimation (`locresBulk`).
