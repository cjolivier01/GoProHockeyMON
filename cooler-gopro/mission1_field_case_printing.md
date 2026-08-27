# Dual MISSION 1 field case

`mission1_field_case_blender.py` procedurally creates every printable part of a
rugged case for two GoPro MISSION 1 cameras and four Enduro 2/HERO13-format
batteries. No downloaded mesh is required or included, and every part fits
within a 250 x 250 mm build area.

Build the complete STL set with:

```sh
make -C cooler-gopro mission1-field-case
```

The lower insert is one flat-topped TPU tray. It has two distinct camera
pockets cut from the local procedural MISSION 1 body—including its offset lens
housing, controls, and rounded body—and four recessed battery pockets. The two
cameras face in opposite directions so the lens lobes nest side by side while
a continuous TPU web keeps the camera pockets separate. Nothing rises above
the tray's top plane.

## Suggested printing

- Base, lid, Pelican-style latches, latch pins, and hinge pin: PETG, ASA, nylon,
  or another impact-tolerant rigid filament; 0.20 mm layers, four walls, and
  25% or greater infill.
- Lower tray, lid retainer, and gasket: TPU 95A, two or three walls, and 15-20%
  infill. The gasket is for dust and splash resistance, not certified
  waterproofing.
- Print the base, tray, retainer, gasket, and lid in their exported
  orientations. Print both pin types on their D-shaped flats. Print the latch
  with its broad face on the bed.
- Print two copies of
  `mission1_field_case_pelican_latch_print_two.stl` and two copies of
  `mission1_field_case_latch_pin_print_two.stl`; print every other STL once.

Printer and filament tolerances vary. Test a camera pocket, battery pocket,
hinge, and latch engagement before relying on the case in the field. Pocket
and pin clearances are constants near the top of the Python generator and can
be tuned without importing or editing an STL.

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

1. Press the lower TPU tray into the base.
2. Seat the TPU gasket in the lid channel and the TPU pad inside the lid.
3. Alternate the base and lid hinge knuckles, then slide in the printed hinge
   pin. A 3 mm metal rod may be substituted for a more durable hinge.
4. Place a latch between each pair of front pivot ears, align the bores, and
   insert one latch pin from the side. Rotate the U-shaped lever upward until
   its cam lip engages the matching lid catch.
5. Load the two cameras into their separate, opposed pockets and place the four
   batteries terminal-down. The continuous lid pad preloads the camera bodies
   and batteries without pressing the shutter buttons.

The dimensions use the local procedural MISSION 1 reference and battery-slot
cross-checks from the existing holder designs linked in the generator's module
documentation. The user-supplied case and Pelican-latch models are functional
and visual precedents only; their meshes are not copied or imported.
