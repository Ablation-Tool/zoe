# Complete iLab integration catalog

This is the use/blocker assessment for every archived iLab source file, source directory, and mirrored web artifact. `Adapt for Zoe` means the mathematics or architecture has a Zoe-specific integration path with new tests; it does not mean the entire legacy program is executed. No artifact is silently omitted.

## Coverage

- Source archive: **8110 entries**, **7790 files**, **82 source directories**, **721 declared programs**, and **148 source images**.
- Web mirror: **30811 artifacts** and **10,338,810,709 downloaded bytes**.
- Mirror failures: **66** artifacts, each retained in `evidence/ilab/catalog.json` with its exact HTTP error.
- Reference VirtualBox image: archived at `/media/cowboy/research/ilab-invt/source/Mandriva-2010-pwp-i586-iLab.7z`.
- Full source and web artifacts remain on the research drive at `/media/cowboy/research/ilab-invt` rather than being injected into Git.

## What Zoe can use and improve

The event-causal engine uses iLab-inspired visual channels, VisualCortex/Brain modularity, temporal surprise, visual memory, component composition, exact graph planning, SPU/Beowulf execution imagery, and reference tests. New Zoe code supplies the missing causal loop: reconstructed event scenes influence goals, candidate futures, values, and reversible actions. SIFT, HMAX, gist, object recognition, DVS hardware, neuromorphic deployment, and physical robotics remain separately validated or optional rather than being claimed as completed capabilities.

## What Zoe cannot currently use, and why

- **Full legacy core build:** currently blocked at `src/Image/JPEGUtil.C` because `jpeglib.h` is unavailable. Configure also reports libpng, FFTW, SDL, OpenCV, Qt, Ice, MATLAB, CUDA, LAPACK, and other optional dependencies missing. The precise log is `analysis/build-core-patched.log` on the research drive.
- **CUDA and CUDASIFT:** no CUDA development toolkit or compatible configured toolchain was found.
- **Qt3/Qt4:** no corresponding development kit was found; Zoe keeps its existing native interfaces.
- **Ice and MATLAB:** required generators and runtime roots are absent.
- **Physical robots, cameras other than `/dev/video0`, servos, GPS, sonar, FireWire, embedded devices, and proprietary middleware:** require the actual device, protocol, owner grant, and independent safety validation.
- **CORBA:** technically unsuitable for Zoe's existing MCP/ACP architecture and missing its legacy runtime.
- **HMAX as production recognition:** iLab's own README reports unsatisfactory natural-image performance and excludes it from the Brain module.
- **Broken or forbidden web links:** all failures remain marked `Blocked` with exact 403/404 evidence; the source tree still supplies the underlying code for many malformed Doxygen links.

## Licensing and patent evidence

The code is GPL version 2 or later. Zoe remains GPL-3.0-only and retains copyright, license, provenance, and modification notices. The 2014 pending-patent notice is historical evidence, not the current legal conclusion: [US8098886B2](https://patents.google.com/patent/US8098886B2/en) lists `Expired - Lifetime` with expiration 2024-05-28, and [US8515131B2](https://patents.google.com/patent/US8515131B2/en) lists `Expired - Fee Related` effective 2025-08-20. These records are not legal advice or an exhaustive patent clearance.

## Every source directory

| Directory | Files | Classes | Programs | Status | Reason and Zoe path |
|---|---:|---:|---:|---|---|
| `src/App3DEye` | 5 | 0 | 2 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/AppDevices` | 49 | 0 | 46 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/AppEye` | 5 | 0 | 3 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/AppGUI` | 2 | 0 | 1 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/AppMedia` | 48 | 0 | 47 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/AppNeuro` | 18 | 0 | 17 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/AppPsycho` | 166 | 0 | 81 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/Apps` | 8 | 0 | 2 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/ArmControl` | 23 | 0 | 11 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Audio` | 4 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/BO` | 11 | 0 | 0 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/BPnnet` | 9 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/BayesFilters` | 6 | 0 | 2 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Forward ensembles and uncertainty; the local UKF compatibility patch remains separately reviewed. |
| `src/BeoSub` | 137 | 0 | 40 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Beobot` | 88 | 0 | 30 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Beowulf` | 14 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Distributed execution architecture and nonnegative graph search; no cluster-runtime claim. |
| `src/CINNIC` | 32 | 0 | 9 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/CMapDemo` | 3 | 0 | 1 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/CUDA` | 105 | 0 | 19 | **Blocked** | Configure found no cuda_runtime.h or CUDA toolkit on this host. A concrete current dependency, compatibility, or hardware constraint prevents use on this host. |
| `src/CUDASIFT` | 20 | 0 | 4 | **Blocked** | CUDA SIFT requires the unavailable CUDA toolkit and compatible GPU toolchain. A concrete current dependency, compatibility, or hardware constraint prevents use on this host. |
| `src/Cell` | 4 | 0 | 1 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. SPU instruction and execution imagery, not a Cell SDK runtime. |
| `src/Channels` | 247 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Visual feature channels and sparse modular event encoding. |
| `src/CmuCam` | 4 | 0 | 1 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Component` | 38 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Composable, guarded event-causal modules with explicit checkpoints. |
| `src/Controllers` | 6 | 0 | 1 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Corba` | 46 | 0 | 8 | **Do not adopt** | CORBA is superseded here by Zoe's existing MCP/ACP and local evidence protocols; the required omniORB libraries are also unavailable. The source or its own documentation supplies a technical reason not to use this as a production Zoe component. |
| `src/Demo` | 10 | 0 | 5 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/Devices` | 117 | 0 | 0 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Embedded` | 43 | 0 | 0 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Envision` | 37 | 0 | 3 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/FeatureMatching` | 16 | 0 | 5 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/Features` | 13 | 0 | 3 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/Fitting` | 7 | 0 | 1 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/Foveator` | 10 | 0 | 1 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/GA` | 6 | 0 | 1 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/GUI` | 55 | 0 | 1 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/GameBoard` | 16 | 0 | 1 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/GenericUtils` | 7 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/Geometry` | 4 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/Gesture` | 2 | 0 | 1 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/Gist` | 44 | 0 | 23 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Low-dimensional scene signatures; no unvalidated semantic scene category claim. |
| `src/HMAX` | 15 | 0 | 10 | **Do not adopt** | The iLab README itself reports unsatisfactory natural-image performance and excludes HMAX from the Brain module; retain it as a research reference, not Zoe's production recognizer. Research comparison only. |
| `src/INVT` | 19 | 0 | 17 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/Ice` | 32 | 0 | 8 | **Blocked** | Configure found no Ice library or slice2cpp/slice2java generators. A concrete current dependency, compatibility, or hardware constraint prevents use on this host. |
| `src/Image` | 158 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Image/event transforms, spatial coherence, and reconstructed scene state. |
| `src/Landmark` | 6 | 0 | 1 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/Learn` | 61 | 0 | 15 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/MBARI` | 20 | 0 | 3 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Matlab` | 46 | 0 | 5 | **Blocked** | Configure found no mex executable or MATLAB root. A concrete current dependency, compatibility, or hardware constraint prevents use on this host. |
| `src/Media` | 74 | 0 | 1 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/ModelNeuron` | 69 | 0 | 9 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/NeovisionII` | 89 | 0 | 27 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Optional smart-camera architecture; Ice-generated services are not currently buildable. |
| `src/Nerdcam` | 5 | 0 | 4 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Neuro` | 175 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. VisualCortex/Brain/VisualBuffer-inspired shared event state and attention. |
| `src/ObjRec` | 35 | 0 | 17 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Future validated landmark/object experiments; conspicuity is not called object recognition. |
| `src/Parallel` | 20 | 0 | 16 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/Psycho` | 72 | 0 | 2 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/Qt` | 119 | 0 | 14 | **Blocked** | Configure found no Qt3 development kit; use Zoe native interfaces instead of adding a legacy GUI dependency. A concrete current dependency, compatibility, or hardware constraint prevents use on this host. |
| `src/Qt4` | 12 | 0 | 1 | **Blocked** | Configure found no Qt4 development kit; use Zoe native interfaces instead of adding a legacy GUI dependency. A concrete current dependency, compatibility, or hardware constraint prevents use on this host. |
| `src/QtUtil` | 7 | 0 | 0 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/RCBot` | 21 | 0 | 11 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Raster` | 55 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/Robots` | 1036 | 0 | 101 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/SIFT` | 42 | 0 | 8 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Future validated landmark matching experiments, not generic semantic recognition. |
| `src/SalGlasses` | 14 | 0 | 1 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Script` | 12 | 0 | 1 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/SeaBee` | 96 | 0 | 21 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/Simulation` | 37 | 0 | 2 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Time-expanded prediction and reversible event execution. |
| `src/SpaceVariant` | 18 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/Surprise` | 22 | 0 | 3 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Prediction-minus-observation surprise and independent uncertainty. |
| `src/TIGS` | 43 | 0 | 3 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/TestSuite` | 22 | 0 | 17 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference tests and independent Zoe comparisons. |
| `src/Transport` | 70 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/Util` | 87 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/VFAT` | 60 | 0 | 14 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/Vgames` | 5 | 0 | 4 | **Run as reference** | Reference source, example, experiment, or test used for comparison rather than directly adopted. Reference source, example, experiment, or test used for comparison rather than directly adopted. |
| `src/Video` | 16 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/nub` | 21 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/pbot` | 1 | 0 | 1 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/plugins` | 80 | 0 | 13 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |
| `src/rutz` | 82 | 0 | 0 | **Adapt for Zoe** | Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim. |
| `src/tcl` | 38 | 0 | 0 | **Optional integration** | Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope. |

## Machine-readable coverage

`evidence/ilab/catalog.json` contains every source-file SHA-256, classification, reason, Zoe path, and every mirrored web artifact including all failures. Regenerate with `python scripts/build-ilab-catalog.py`.
