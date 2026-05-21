[Repository home](../README.md) · [Installation](installation.md) · [Quick start](quick-start.md) · [CLI reference](reference/cli.md) · [Troubleshooting](troubleshooting.md)

---

# 3D Class reassignment

<p align="center">
  <img src="images/fig1B.png" alt="fig1B.png" width="600">
</p>

3D class reassignment refines particle membership across a set of user-provided reference maps. The input maps usually come from a previous 3D classification step and represent alternative conformational states, but they can also be generated using different masks, refinements, or processing strategies.

JANAS compares each particle with reprojections from every reference map using the Structural Cross-correlation Index (SCI). Each particle is then assigned to the class that best matches its structural signal. This can correct particle misassignment from an initial classification and reduce differences in class quality, especially when classes contain related conformations, minority states, or particles affected by local heterogeneity.

After reassignment, each class can be reconstructed directly or passed to iterative particle selection. This per-class selection step can further improve the coherence of each state before downstream refinement, inspection, or another round of classification.


## Quick start

### Create & Launch the session manager

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

Output: `reclassify/final_classes/`

> **Note on `--noExternalPrograms`:** with this flag, JANAS performs 3D reconstruction and local resolution estimation using its own internal code (no external dependencies; a GPU is strongly recommended for medium-to-large datasets). Without `--noExternalPrograms`, JANAS will try to call RELION for these steps — make sure RELION is installed and accessible on your `PATH` before running.

## About `--mpi`

`--mpi` sets the number of parallel worker processes used during particle scoring. The requested value is automatically capped to a safe one at runtime:

1. If `--mpi` is greater than the number of available CPU cores, it is reduced to the CPU count (`multiprocessing.cpu_count()`). For example, requesting `--mpi 50` on a machine with 20 cores will use 20.
2. If `--mpi` is less than 1, it is raised to 1.
3. If `--mpi` is greater than the number of particles being processed, it is reduced to the particle count.

This means you can safely set `--mpi` to a generous value and JANAS will pick the largest reasonable number of workers without over-subscribing the machine. For best performance, set `--mpi` to the number of physical cores you want to dedicate to the run.
