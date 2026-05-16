# JANAS

JANAS is a command-line toolkit for iterative particle scoring and classification in single-particle cryo-EM. It uses per-particle Structural Cross-correlation Index (SCI) to rank and select those images that contribute most to local map quality, and to reassigns particles to pre-computed 3D conformations to resolve heterogeneity. By focusing each reconstruction on high-quality, class-specific subsets, JANAS refines the final maps and enhances the reliability of downstream model building.


## Notice to Users

We are actively working to enhance JANAS’s user-friendliness and ensure broader compatibility across different systems. As the code is currently under review and development, some functions may still be in testing or require specific configurations for optimal performance. If you encounter any issues or require assistance in setting up or using JANAS, please do not hesitate to reach out at mauro.maiorca@cssb-hamburg.de. Your feedback is valuable and will contribute to refining the software for the release v0.2.0 coming up soon.

## Compile and Install

[Compile and Install JANAS apps](tutorial/INSTALL_APPS.md)

[Compile and Install JANAS core](tutorial/INSTALL_CORE_python.md)

[Accessory External Programs](tutorial/accessory_programs.md)

# Usage:

## Preparare your dataset for JANAS

JANAS operates on the standard RELION 3.1 STAR‐plus‐MRC(S) format, which requires a .star file listing the particles and one or more .mrcs stacks in which each 2D image represents a particle.

If you coming from cryoSPARC, first export your particles as an .mrcs stack and generate a minimal RELION STAR file ([details here](tutorial/import_stack_from_cs.md) )

In the process of creating the desired stack, you can use janas_app_starProcess to manipulate the STAR file, by performing actions such as randomizing or reassigning subsets, deleting, renaming, or reordering labels, and filtering particles by class name. Additionally, it enables export to CSV/VEM, IMOD Xf, or cryoEF .dat angle files and comparison of two STAR files to identify particles with similar coordinates.

## Overview

JANAS apps and utils can be used independently for specific analysis of the stack, that goes from inspecting the partcle numbers and distribution of particles in half maps (`janas_app_starProcess --i partcles.star --info`), to randomize half maps (`janas_utils randomize_halves`), or compute automatic crop of an image based on a given mask (`janas_utils maskedCrop`). 

With `janas_session_manager` it possible to create a bash script with the full pileline for iterative particle selection (`janas_session_manager new_select_session`) or 3D class reassignment (`janas_session_manager classification_session`)

## Tutorial

A simplified, step-by-step practical example of using JANAS on the serotonin 5-HT1B–Go receptor complex (EMPIAR-10308)—illustrating how to discriminate a high-populated conformational state vs a low-populated conformational state through targeted 3D class reassignment and iterative particle selection—is available in the [tutorial](tutorial/README.md).

# key commands:
### Create a session for iterative particle selection using SCI scoring function for selection, and script files to run
go in the directory where you want the new project to be created and call the following command:
```
janas_session_manager new_select_session \
            --name J182_janas \
            --particles J185_particlesStack.star \
            --map maps/J182_003_volume_map_half_A.mrc \
            --map2 maps/J182_003_volume_map_half_B.mrc \
            --mask maps/J185_maskLocal.mrc \
            --angpix 0.8400 \
            --numRecs 4 #default is 10
```
it creates a directory with the given name ("J182_janas" in the example), and a script file to run, in this case J182_janas_run.sh


### Create a session for 3D class reassignment, starting with initial lower resolution maps
go in the directory where you want the reclassification to be created and call the following command:
```
janas_session_manager classification_session  \
            --name reclassification  \
            --particles particlesStack.star \
            --mask mask.mrc \
            --maps class1.mrc class2.mrc class3.mrc class4.mrc \
            --angpix 0.8400 \
            --mpi 85
reclassification/reclassification_run.sh
```


### Create a session for random particle selection, and script files to run
go in the directory where you want the session to be created and call the following command:
```
janas_session_manager random_selection_session \
                        --name J188_fullMask_random \
                        --particles J188_fullMask_janas_target.star \
                        --mask maps/J188_mask0577_dilated.mrc \
                        --dir J188_fullMask_janas
./J188_fullMask_janas/J188_fullMask_random_run.sh
```


