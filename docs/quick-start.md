[Repository home](../README.md) · [Docs home](index.md) · [Installation](installation.md) · [CLI reference](reference/cli.md) · [Troubleshooting](troubleshooting.md)

---

# Quick start

This page covers the minimum steps to run each workflow. For a complete worked example, see the [EMPIAR-10308 tutorial](examples/empiar-10308.md).

## Input requirements

JANAS expects RELION 3.1 STAR+MRC(S) format:

- A `.star` file listing particles with Euler angles, CTF parameters, and image references
- One or more `.mrcs` stacks containing the 2D particle images
- A 3D mask in `.mrc` format

If your particles come from cryoSPARC, convert them first with `janas_utils csparc2star-stack`. See [CryoSPARC integration](workflows/cryosparc.md).

## Iterative particle selection

Create a selection session and run it:

```bash
janas_session_manager new_select_session \
    --name my_selection \
    --particles particles.star \
    --map halfA.mrc \
    --map2 halfB.mrc \
    --mask mask.mrc \
    --mpi 40 \
    --noExternalPrograms

./my_selection/my_selection_run.sh
```

> **Note on `--noExternalPrograms`:** with this flag, JANAS performs 3D reconstruction and local resolution estimation using its own internal code (no external dependencies; a GPU is strongly recommended for medium-to-large datasets). Without `--noExternalPrograms`, JANAS will try to call RELION for these steps — make sure RELION is installed and accessible on your `PATH` before running.

The session manager creates a working directory with a run script and configuration file. The script iterates through scoring, subsetting, reconstruction, and local resolution evaluation until convergence.

**Output:** `my_selection/reference_subset.star` — the selected particle subset.

To view a summary of the optimisation:

```bash
janas_optimizer plotOverview --overview my_selection/overview.txt --plot
```

For details on parameters and how the selection loop works, see [Iterative particle selection](workflows/selection.md).

## 3D class reassignment

Create a classification session and run it:

```bash
janas_session_manager classification_session \
    --name reclassify \
    --particles particles.star \
    --maps class1.mrc class2.mrc class3.mrc \
    --mask mask.mrc \
    --mpi 40 \
    --noExternalPrograms

./reclassify/reclassify_run.sh
```

> Same note about `--noExternalPrograms` as above — without it, RELION must be installed and on your `PATH`.

JANAS equalises the amplitudes across all reference maps, scores each particle against every map, assigns each particle to the class with the highest SCI, and reconstructs per-class volumes.

**Output:** `reclassify/final_classes/` — per-class star files and half-map reconstructions.

For details, see [3D class reassignment](workflows/classification.md).

## Inspecting STAR files

```bash
janas_app_starProcess --i particles.star --info
```

This prints the number of particles, column labels, and subset distribution.

---

[Back to documentation index](index.md)
