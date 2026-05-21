[Repository home](../README.md) · [Installation](installation.md) · [Quick start](quick-start.md) · [CLI reference](reference/cli.md) · [Troubleshooting](troubleshooting.md)

---

# ITERATIVE SELECTION

<p align="center">
  <img src="images/fig1A.png" alt="fig1A.png" width="600">
</p>

## Quick start

### Create & Launch the session manager

```bash
janas_session_manager new_select_session \
    --name my_selection \
    --particles particles.star \
    --map halfA.mrc \
    --map2 halfB.mrc \
    --mask mask.mrc \
    --mpi 40

./my_selection/my_selection_run.sh
```
