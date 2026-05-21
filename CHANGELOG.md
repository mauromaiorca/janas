# Changelog

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
