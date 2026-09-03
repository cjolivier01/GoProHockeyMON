# GoProHockeyMON 3D-printable models

This library contains the printable camera hardware that complements the
GoProHockeyMON remote. Each primary design owns a directory, its generator,
documentation, and generated print files. Shared standards and attributed
reference geometry live in [`common/`](common/).

## Model catalog

| Model | Purpose | Build target |
| --- | --- | --- |
| [`dual-fan/`](dual-fan/) | Parametric one-to-three-fan holder with detachable two- and three-prong GoPro adapters | `dual-fan` |
| [`fan-case/`](fan-case/) | Cooled GoPro shell with removable insert, controls, retainers, and optional acoustic cartridge | `fan-case` |
| [`fan-silencer/`](fan-silencer/) | Four-hole fan silencers for 40, 60, 80, and 120 mm fans | `fan-silencer` |
| [`hockeymon-camera-case/`](hockeymon-camera-case/) | Multi-camera HockeyMON enclosure with configurable mounts, fans, and service panels | `hockeymon-camera-case` |
| [`mission1-field-case/`](mission1-field-case/) | Rugged two-camera MISSION 1 transport case with TPU inserts, gasket, latches, and multicolor lid project | `mission1-field-case` |
| [`mission1-dummy/`](mission1-dummy/) | Printable MISSION 1 reference body used for fit checks and by other generators | `mission1-dummy` |
| [`horn/`](horn/) | Parametric airflow horn | `horn` |
| [`flat-fan-cover/`](flat-fan-cover/) | Low-profile fan cover | `flat-fan-cover` |
| [`wrapping-fan-cover/`](wrapping-fan-cover/) | Wraparound fan cover | `wrapping-fan-cover` |

The `hockeymom_*` filenames are retained for compatibility with existing
prints and automation; the model is presented as the HockeyMON camera case.

## Build

GNU Make 4.3 or newer and Blender are required for printable geometry. From
the repository root:

```sh
make -C models3d                 # list model and documentation targets
make -C models3d dual-fan
make -C models3d fan-case
make -C models3d hockeymon-camera-case
make -C models3d mission1-field-case
```

Generated STL, 3MF, Blender, PDF, and render files are ignored by Git. They
are written into the directory for the model that produced them.

Dimension guides can be generated and checked independently:

```sh
make -C models3d dual-fan-dim-pdf check-dual-fan-dim-pdf-sync
make -C models3d fan-case-dim-pdf check-fan-case-dim-pdf-sync
make -C models3d dim-pdf check-dim-pdf-sync
```

## Shared material

`common/fan_size_presets.py` is the single source of truth for standard fan
dimensions used across model generators. The embedded Thingiverse reference
mesh in `common/thingiverse_5177333_fan_intake_mk4_reference.py` retains its
source attribution and license metadata for the fan-silencer adaptation.
