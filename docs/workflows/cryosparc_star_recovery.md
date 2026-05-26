# CryoSPARC particle STAR recovery

Convert particle metadata exported from CryoSPARC into a RELION/JANAS-compatible STAR file, adjust the stack reference, and (optionally) restore the original source-particle provenance after stack-based processing.

**When to use this.** Particles were consolidated into a single `.mrcs` stack using JANAS, processed in CryoSPARC, and exported back as metadata. The exported STAR file points to the consolidated stack rather than to the original particle stacks. If provenance was recorded during stack creation, `backmap_stars` restores the original references.

**Workflow overview:**

```text
CryoSPARC .cs
     │  (1) csparc2star         → convert to STAR
     ▼
.star  (CryoSPARC-internal path)
     │  (2) --stackRename       → adjust stack path
     ▼
.star  (consolidated stack)

     │  (3) backmap_stars       → Optional restore original provenance
     ▼
.star  (original source particles)
```

---

## Step 1 — Convert the CryoSPARC `.cs` file to STAR

**Why:** CryoSPARC exports particle metadata in its own `.cs` binary format, which RELION and JANAS cannot read directly.

**Command:**

```bash
janas_utils csparc2star \
  class_J1003_4028particles/J1003_003_particles.cs \
  class_J1003_4028particles/J1003_003_particles.star
```

**Result:** a RELION-style `.star` file containing particle image references, orientations, shifts, CTF parameters and class assignments. A typical `_rlnImageName` entry looks like:

```text
000022@J1001/imported/008248594774147691034_EMPIAR_12707_stack.mrcs
```

This path points to a CryoSPARC-internal symbolic link rather than to the original `.mrcs` file. To see the link target:

```bash
ls -l J1001/imported/008248594774147691034_EMPIAR_12707_stack.mrcs
```

which may return:

```text
J1001/imported/008248594774147691034_EMPIAR_12707_stack.mrcs -> \
/gpfs/cssb/user/maiorcam/cryoSPARC/Import/figureMaps_emprove_selection_adptiveMask/remaining_selection3Ite2/EMPIAR_12707_stack.mrcs
```

The effective stack file is therefore `EMPIAR_12707_stack.mrcs`.

---

## Step 2 — Adjust the stack name in `_rlnImageName`

**Why:** CryoSPARC writes the stack path as an internal symbolic link. This link breaks when the STAR file is moved or shared, so it is preferable to point `_rlnImageName` directly at the consolidated stack.

**Command:**

```bash
emprove_app_starProcess \
  --i class_J1003_4028particles/J1003_003_particles.star \
  --stackRename EMPIAR_12707_stack.mrcs \
  --o class_J1003_4028particles/J1003_003_particlesStack.star
```

**Result:** the same particle metadata as the converted CryoSPARC STAR file, but `_rlnImageName` now points directly to the consolidated stack:

```text
000022@EMPIAR_12707_stack.mrcs
```

This makes the STAR file portable: downstream tools find the stack directly rather than resolving the CryoSPARC-internal symbolic link shown in Step 1.

This step fixes the stack path only. It does not restore the original source-particle names.

---

## Step 3 — Optionally Restore the original source-particle image names

**Why:** stack-based processing references the consolidated stack, not the original particles. If you want to bring the stack back, and keep using in your pipeline, you might want to restores the original provenance so that the final STAR file points back to the source particles.

**Background.** If the consolidated stack was created from an original STAR file, each particle originally had an `_rlnImageName` such as:

```text
009619@J1149/restack/batch_6_restacked.mrc
```

During stack creation this was replaced by a consolidated-stack reference such as:

```text
000001@EMPIAR_12707_stack.mrcs
```

When JANAS creates the consolidated stack with provenance tracking, the stack-generation STAR file retains the original source image name in the `_janas_source_rlnImageName` column:

```text
_rlnImageName                    _janas_source_rlnImageName
000001@EMPIAR_12707_stack.mrcs   009619@J1149/restack/batch_6_restacked.mrc
000002@EMPIAR_12707_stack.mrcs   009620@J1149/restack/batch_6_restacked.mrc
000003@EMPIAR_12707_stack.mrcs   009621@J1149/restack/batch_6_restacked.mrc
```

Downstream processing may discard `_janas_source_rlnImageName`. In that case the processed STAR file still points to the consolidated stack, and the original source-particle names are no longer present. `backmap_stars` restores them using the stack-generation STAR file as a lookup table.

**Command:**

```bash
janas_utils backmap_stars \
  --mapping ../original_stack/EMPIAR_12707_stack.star \
  --processed class_J1003_4028particles/J1003_003_particlesStack.star \
  --output class_J1003_4028particles/J1003_003_particlesOriginalParticles.star
```

**Arguments:**

- `--mapping` — the STAR file produced when the consolidated stack was created. It must contain both `_rlnImageName` and `_janas_source_rlnImageName`.
- `--processed` — the processed STAR file to fix. Its `_rlnImageName` values point to the consolidated stack (e.g. `000022@EMPIAR_12707_stack.mrcs`).
- `--output` — the corrected STAR file, with `_rlnImageName` restored to the original source references.

**Result:** each consolidated-stack reference is replaced by its original source-particle name. For example:

```text
000022@EMPIAR_12707_stack.mrcs
```

becomes:

```text
009640@J1149/restack/batch_6_restacked.mrc
```

By default the command also writes an audit column, `_janas_stack_rlnImageName`, recording the previous consolidated-stack reference (e.g. `000022@EMPIAR_12707_stack.mrcs`). The output is therefore fully traceable: `_rlnImageName` points back to the original particle, while `_janas_stack_rlnImageName` records the consolidated-stack particle used for the mapping.

---

## Strict mapping

By default, `backmap_stars` runs in **strict mode**: every `_rlnImageName` in the processed STAR file must be found in the mapping STAR file. If a particle cannot be mapped, the command stops with an error. This is the safest behaviour, as it prevents generation of a partially corrected STAR file.

For debugging, strict mode can be disabled with `--no-strict`:

```bash
janas_utils backmap_stars \
  --mapping ../original_stack/EMPIAR_12707_stack.star \
  --processed class_J1003_4028particles/J1003_003_particlesStack.star \
  --output class_J1003_4028particles/J1003_003_particlesOriginalParticles.star \
  --no-strict
```

With `--no-strict`, unmapped particles are left unchanged. Use this only to inspect problematic datasets, not for routine processing.

---

## Complete command sequence

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

# 3. Restore the original source-particle image names
janas_utils backmap_stars \
  --mapping ../original_stack/EMPIAR_12707_stack.star \
  --processed class_J1003_4028particles/J1003_003_particlesStack.star \
  --output class_J1003_4028particles/J1003_003_particlesOriginalParticles.star
```

The final STAR file to use in subsequent RELION or JANAS steps is:

```text
class_J1003_4028particles/J1003_003_particlesOriginalParticles.star
```

---

## Summary

| File | Role |
|------|------|
| `J1003_003_particles.star` | Converted from the CryoSPARC `.cs` file. May still contain CryoSPARC-internal stack paths. |
| `J1003_003_particlesStack.star` | `_rlnImageName` adjusted to `EMPIAR_12707_stack.mrcs`. |
| `J1003_003_particlesOriginalParticles.star` | `_rlnImageName` restored to the original source-particle references. |

In short:

- `--stackRename` (Step 2) fixes the stack path.
- `backmap_stars` (Step 3) restores the original particle provenance.

---

> **Note on command naming.** During the transition from the former name (EMPROVE) to JANAS, some commands still carry the `emprove_` prefix (for example, `emprove_app_starProcess`) as backward-compatible aliases. Equivalent `janas_`-prefixed commands are being introduced; either form can be used during the transition. This note will be removed once the renaming is complete across the command set.
