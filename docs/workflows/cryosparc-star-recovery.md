# CryoSPARC particle STAR recovery

This tutorial describes how to convert particle metadata exported from CryoSPARC into a RELION/JANAS-compatible STAR file, normalise the stack path written in `_rlnImageName`, and restore the original source particle references after processing a consolidated stack.

This workflow is useful when particles were first collected into a single `.mrcs` stack using JANAS, processed in CryoSPARC, and then exported back as particle metadata. In this situation, the STAR file produced from CryoSPARC may still point to the consolidated stack rather than to the original particle stacks. If the original particle provenance was stored during stack creation, it can be restored with `backmap_stars`.

The workflow has three steps:

1. Convert the CryoSPARC `.cs` file to STAR format.
2. Replace CryoSPARC's internal stack path with the original consolidated stack name.
3. Back-map the consolidated-stack particle references to the original source particle references.

## 1. Convert the CryoSPARC `.cs` file to STAR format

The first step is to convert the CryoSPARC `.cs` particle file into a RELION-style `.star` file:

```bash
janas_utils csparc2star \
  class_J1003_4028particles/J1003_003_particles.cs \
  class_J1003_4028particles/J1003_003_particles.star
```

The generated STAR file contains the particle metadata exported from CryoSPARC, including particle image references, orientations, shifts, CTF parameters and class assignments.

A typical `_rlnImageName` entry may look like this:

```text
000022@J1001/imported/008248594774147691034_EMPIAR_12707_stack.mrcs
```

This is not necessarily wrong. CryoSPARC often stores imported stacks inside the job directory using symbolic links. The path written in `_rlnImageName` may therefore point to a CryoSPARC-internal link rather than directly to the original `.mrcs` file.

For example:

```bash
ls -l J1001/imported/008248594774147691034_EMPIAR_12707_stack.mrcs
```

may return:

```text
J1001/imported/008248594774147691034_EMPIAR_12707_stack.mrcs -> \
/gpfs/cssb/user/maiorcam/cryoSPARC/Import/figureMaps_emprove_selection_adptiveMask/remaining_selection3Ite2/EMPIAR_12707_stack.mrcs
```

In this example, the effective stack file is:

```text
EMPIAR_12707_stack.mrcs
```

## 2. Normalise the stack name in `_rlnImageName`

For subsequent RELION or JANAS processing, it is often preferable to replace the CryoSPARC-internal stack path with the direct name of the consolidated stack.

This can be done with `emprove_app_starProcess` using `--stackRename`:

```bash
emprove_app_starProcess \
  --i class_J1003_4028particles/J1003_003_particles.star \
  --stackRename EMPIAR_12707_stack.mrcs \
  --o class_J1003_4028particles/J1003_003_particlesStack.star
```

The resulting file:

```text
class_J1003_4028particles/J1003_003_particlesStack.star
```

contains the same particle metadata as the converted CryoSPARC STAR file, but the `_rlnImageName` entries now point directly to the consolidated stack:

```text
000022@EMPIAR_12707_stack.mrcs
```

This makes the STAR file more portable. Without this correction, downstream tools may try to find the particle stack inside the CryoSPARC project directory, for example:

```text
000022@J1001/imported/008248594774147691034_EMPIAR_12707_stack.mrcs
```

rather than in the expected working directory or original stack location.

This step only fixes the stack path. It does not restore the original source particle names.

## 3. Restore the original source particle image names

If the consolidated stack was created from an original STAR file, each particle originally had an `_rlnImageName` such as:

```text
009619@J1149/restack/batch_6_restacked.mrc
```

During stack creation, this was replaced by a consolidated-stack reference such as:

```text
000001@EMPIAR_12707_stack.mrcs
```

When JANAS creates the consolidated stack with provenance tracking, the stack-generation STAR file keeps the original source image name in:

```text
_janas_source_rlnImageName
```

For example, the stack-generation STAR file contains a mapping of the form:

```text
_rlnImageName                    _janas_source_rlnImageName
000001@EMPIAR_12707_stack.mrcs   009619@J1149/restack/batch_6_restacked.mrc
000002@EMPIAR_12707_stack.mrcs   009620@J1149/restack/batch_6_restacked.mrc
000003@EMPIAR_12707_stack.mrcs   009621@J1149/restack/batch_6_restacked.mrc
```

However, downstream processing may remove `_janas_source_rlnImageName`. In that case, the processed STAR file still points to the consolidated stack, but the original source particle names are no longer present.

The `backmap_stars` command restores them by using the stack-generation STAR file as a lookup table.

In this example, the command is:

```bash
janas_utils backmap_stars \
  --mapping ../original_stack/EMPIAR_12707_stack.star \
  --processed class_J1003_4028particles/J1003_003_particlesStack.star \
  --output class_J1003_4028particles/J1003_003_particlesOriginalParticles.star
```

Here:

```text
../original_stack/EMPIAR_12707_stack.star
```

is the STAR file produced when the consolidated stack was created. It must contain both:

```text
_rlnImageName
_janas_source_rlnImageName
```

The file:

```text
class_J1003_4028particles/J1003_003_particlesStack.star
```

is the processed STAR file to fix. Its `_rlnImageName` values point to the consolidated stack:

```text
000022@EMPIAR_12707_stack.mrcs
```

The output file:

```text
class_J1003_4028particles/J1003_003_particlesOriginalParticles.star
```

contains the same processed particle metadata, but with `_rlnImageName` restored to the original source particle references.

For example:

```text
000022@EMPIAR_12707_stack.mrcs
```

is replaced by the corresponding original particle name from the mapping STAR file, such as:

```text
009640@J1149/restack/batch_6_restacked.mrc
```

The command also writes an audit column by default:

```text
_janas_stack_rlnImageName
```

This column stores the previous consolidated-stack reference, for example:

```text
000022@EMPIAR_12707_stack.mrcs
```

This makes the output traceable: `_rlnImageName` points back to the original particle, while `_janas_stack_rlnImageName` records the consolidated-stack particle used for the mapping.

## Complete command sequence

The full workflow is:

```bash
# 1. Convert CryoSPARC particle metadata to STAR format
janas_utils csparc2star \
  class_J1003_4028particles/J1003_003_particles.cs \
  class_J1003_4028particles/J1003_003_particles.star

# 2. Replace the CryoSPARC-internal stack path with the consolidated stack name
emprove_app_starProcess \
  --i class_J1003_4028particles/J1003_003_particles.star \
  --stackRename EMPIAR_12707_stack.mrcs \
  --o class_J1003_4028particles/J1003_003_particlesStack.star

# 3. Restore the original source particle image names
janas_utils backmap_stars \
  --mapping ../original_stack/EMPIAR_12707_stack.star \
  --processed class_J1003_4028particles/J1003_003_particlesStack.star \
  --output class_J1003_4028particles/J1003_003_particlesOriginalParticles.star
```

The final STAR file to use in subsequent RELION or JANAS steps is:

```text
class_J1003_4028particles/J1003_003_particlesOriginalParticles.star
```

## Notes on strict mapping

By default, `backmap_stars` runs in strict mode. This means that every `_rlnImageName` in the processed STAR file must be found in the mapping STAR file.

If a particle cannot be mapped, the command stops with an error. This is the safest behaviour because it prevents generation of a partially corrected STAR file.

For debugging, strict mode can be disabled:

```bash
janas_utils backmap_stars \
  --mapping ../original_stack/EMPIAR_12707_stack.star \
  --processed class_J1003_4028particles/J1003_003_particlesStack.star \
  --output class_J1003_4028particles/J1003_003_particlesOriginalParticles.star \
  --no-strict
```

With `--no-strict`, unmapped particles are left unchanged. This should only be used to inspect problematic datasets, not for routine processing.

## Summary

The three files have different roles:

| File | Role |
|------|------|
| `J1003_003_particles.star` | STAR file converted from the CryoSPARC `.cs` file. It may still contain CryoSPARC-internal stack paths. |
| `J1003_003_particlesStack.star` | STAR file with `_rlnImageName` normalised to `EMPIAR_12707_stack.mrcs`. |
| `J1003_003_particlesOriginalParticles.star` | STAR file with `_rlnImageName` restored to the original source particle references. |

The first correction, `--stackRename`, fixes the stack path.

The second correction, `backmap_stars`, restores the original particle provenance.
