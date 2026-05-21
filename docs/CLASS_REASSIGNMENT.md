[Repository home](../README.md) · [Installation](installation.md) · [Quick start](quick-start.md) · [CLI reference](reference/cli.md) · [Troubleshooting](troubleshooting.md)

---

# 3D Class reassignment

<p align="center">
  <img src="images/fig1A.png" alt="fig1A.png" width="600">
</p>

## Quick start

### Create & Launch the session manager

```bash
janas_session_manager classification_session \
    --name reclassify \
    --particles particles.star \
    --maps class1.mrc class2.mrc class3.mrc \
    --mask mask.mrc \
    --mpi 40

./reclassify/reclassify_run.sh
```

Output: `reclassify/final_classes/`
