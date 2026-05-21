[Repository home](../README.md) · [Documentation index](index.md) · [Installation](installation.md) · [CLI reference](reference/cli.md) · [Troubleshooting](troubleshooting.md)

---

# Accessory utilities

JANAS bundles a number of stand-alone utilities for common cryo-EM map and stack operations. They are invoked through `janas_utils <subcommand>` (except `janas_reconstructor`, which is its own command). Use `janas_utils <subcommand> --help` for the full option list.

## sigma_estimate

Estimate a suitable Gaussian sigma for SCI scoring from a pair of half-maps. The value can then be passed to `--sigma` in session-manager and scoring commands.

```bash
janas_utils sigma_estimate halfmap1.mrc halfmap2.mrc
```

## compare_maps

Compare two 3D maps using cross-correlation and related similarity measures (optionally inside a mask).

```bash
janas_utils compare_maps map1.mrc map2.mrc [--mask mask.mrc]
```

## csparc2star-stack

Convert a CryoSPARC `.cs` file into a RELION-style STAR file and assemble a consolidated `.mrcs` particle stack from the original cryoSPARC stack locations.

```bash
janas_utils csparc2star-stack /path/to/particles.cs output_prefix
```

Produces `output_prefix.star` and `output_prefix.mrcs`. See also the [CryoSPARC integration guide](workflows/cryosparc.md).

## clip blur

Gaussian blur a 3D volume with a sigma specified in Ångström.

```bash
janas_utils clip blur in.mrc out.mrc SIGMA_A
```

## clip bfac

B-factor weighting (sharpening) of a 3D volume. Automatic mode estimates the B-factor from the two half-maps; user-driven mode applies a specified B-value.

```bash
# Automatic
janas_utils clip bfac half1.mrc half2.mrc out.mrc

# User-driven
janas_utils clip bfac half1.mrc half2.mrc out.mrc BVALUE
```

## fsc

Compute the Fourier Shell Correlation (FSC) between one or more half-map pairs.

```bash
janas_utils fsc half1.mrc half2.mrc
```

## locres

Compute a local-resolution map from a pair of half-maps. Writes `*_locres.mrc` and auxiliary files.

```bash
janas_utils locres half1.mrc half2.mrc [--mask mask.mrc]
```

For bulk processing of many half-map pairs (used internally by the selection workflow), see `janas_utils locresBulk`.

## project_map

Project a 3D reference map at each particle pose listed in a STAR file and write the resulting 2D reprojections to disk.

```bash
janas_utils project_map --i particles.star --map reference.mrc --o reprojections.mrcs
```

## janas_reconstructor

Internal 3D reconstruction from scored particles. Supports GPU acceleration (PyTorch CUDA, mini-batched) or CPU multiprocessing. Used automatically by the session-manager workflows when `--noExternalPrograms` is set.

```bash
janas_reconstructor \
    --i particles.star \
    --o output.mrc \
    --gpu 0 1 \
    --gpu-batch 20
```

See the [CLI reference](reference/cli.md#janas_reconstructor) for the full option list.

---

[Back to documentation index](index.md)
