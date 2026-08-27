# Dual MISSION 1 field case

`mission1_field_case_blender.py` procedurally creates a rugged case for two
GoPro MISSION 1 cameras, four Enduro 2/HERO13-format batteries, and two cased
Waveshare ESP32-S3 Touch AMOLED 1.75 remotes. No downloaded mesh is required or
included. Every printable part fits within a 250 x 250 mm build area.

Build the complete STL set with:

```sh
make mission1-field-case
```

The command generates the base, lid, removable lower insert, TPU lid retainer,
TPU gasket, latch, hinge pin, title inlay, and subtitle inlay. Print two copies
of `mission1_field_case_latch_print_two.stl`; every other STL is printed once.

## Suggested printing

- Base, lid, lower insert, and hinge pin: PETG, ASA, or another impact-tolerant
  rigid filament; 0.20 mm layers, four walls, and 25% or greater infill.
- Latches: PETG or nylon with the layer lines running along the 28 mm width.
- Gasket and lid retainer: TPU 95A, two or three walls, and 15% infill. The
  gasket is for dust and splash resistance, not certified waterproofing.
- Print the base, insert, retainer, gasket, and lid in their exported
  orientations. Print the hinge pin on its D-shaped flat.

Printer and filament tolerances vary. Before relying on the case in the field,
test one battery pocket, one remote pocket, the hinge, and the latch engagement.
The pocket clearances are constants near the top of the Python generator and
can be tuned without importing or editing an STL.

## Multicolor lid

Import these three files together as a single multi-part object without moving
them relative to one another:

- `mission1_field_case_lid.stl`
- `mission1_field_case_lid_title_inlay.stl`
- `mission1_field_case_lid_subtitle_inlay.stl`

Assign a shell color to the lid and separate colors to the title and subtitle.
The inlays are 0.8 mm deep and sit flush in matching recesses. A multi-material
printer can print all three parts together; with a single-material printer,
print the inlays separately and bond them into the recesses.

## Assembly

1. Press the lower insert into the base.
2. Seat the TPU gasket in the lid channel and the TPU retainer inside the lid.
3. Alternate the base and lid hinge knuckles, then slide in the printed pin. A
   3 mm metal rod may be substituted for a more durable hinge.
4. Snap one printed latch over each aligned front rail.
5. Load cameras lens-up, batteries terminal-down, and remotes screen-down. The
   TPU pads preload the protected faces when the lid closes.

The dimensions use the local procedural MISSION 1 reference, Waveshare's
official 51 x 12.1 mm cased-device drawing, and cross-checks from existing
GoPro battery-holder designs linked in the generator's module documentation.
