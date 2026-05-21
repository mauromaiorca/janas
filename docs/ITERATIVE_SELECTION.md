[Repository home](../README.md) · [Installation](installation.md) · [Quick start](quick-start.md) · [CLI reference](reference/cli.md) · [Troubleshooting](troubleshooting.md)

---

# Iterative Selection

<p align="center">
  <img src="images/fig1A.png" alt="fig1A.png" width="600">
</p>

Iterative selection identifies a particle subset that aims to support a more interpretable reconstruction. Starting from an input particle stack (and ideally reference half maps, and mask), JANAS scores particles using the Structural Cross-correlation Index (SCI), ranks them while accounting for angular distribution, and evaluates candidate particle subsets through repeated reconstruction.

Rather than selecting a fixed percentage of particles, JANAS searches for the particle count that gives the most favourable local-resolution behaviour within the masked region. This allows the workflow to retain particles that contribute consistently to the reconstruction while excluding particles that reduce map quality or introduce artefacts.


## Quick start

### Create & Launch the session manager

```bash
janas_session_manager new_select_session \
    --name my_selection \
    --particles particles.star \
    --map halfA.mrc \
    --map2 halfB.mrc \
    --mask mask.mrc \
    --mpi 40 \
    --noExternalPrograms --gpu 0 1

./my_selection/my_selection_run.sh
```

> **Note on `--noExternalPrograms` and `--gpu`:** with `--noExternalPrograms`, JANAS performs 3D reconstruction and local resolution estimation using its own internal code (no external dependencies). `--gpu 0 1` distributes reconstruction across two GPUs (one per half-map) and gives the best throughput; use `--gpu 0` for a single GPU, or omit `--gpu` entirely to run on CPU only — JANAS still works without a GPU. Without `--noExternalPrograms`, JANAS will try to call RELION for these steps — make sure RELION is installed and accessible on your `PATH` before running.

## About `--mpi`

`--mpi` sets the number of parallel worker processes used during particle scoring. The requested value is automatically capped to a safe one at runtime:

1. If `--mpi` is greater than the number of available CPU cores, it is reduced to the CPU count (`multiprocessing.cpu_count()`). For example, requesting `--mpi 50` on a machine with 20 cores will use 20.
2. If `--mpi` is less than 1, it is raised to 1.
3. If `--mpi` is greater than the number of particles being processed, it is reduced to the particle count.

This means you can safely set `--mpi` to a generous value and JANAS will pick the largest reasonable number of workers without over-subscribing the machine. For best performance, set `--mpi` to the number of physical cores you want to dedicate to the run.
