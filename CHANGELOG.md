# Changelog

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
