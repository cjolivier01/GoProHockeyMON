# Dual MISSION 1 field case

`mission1_field_case_blender.py` procedurally creates every printable part of a
rugged case for two GoPro MISSION 1 cameras and four Enduro 2/HERO13-format
batteries. No downloaded mesh is required or included, and every part fits
within a 250 x 250 mm build area.

Build the complete STL set and AMS-ready project with:

```sh
make -C cooler-gopro mission1-field-case
```

The Makefile requires GNU Make 4.3 or newer. On macOS, install a current GNU
Make and run the command as `gmake` when the system `make` is BSD Make.

The lower insert is one flat-topped TPU tray. It has two distinct camera
pockets cut from the local procedural MISSION 1 body—including its offset lens
housing, controls, and rounded body—and four recessed battery pockets. The two
cameras face in opposite directions so the lens lobes nest side by side while
a continuous TPU web keeps the camera pockets separate. Nothing rises above
the tray's top plane. Each lens end widens into a trapezoidal relief for the
soft MISSION 1 Pro lens-flare/hood attachment shown in the supplied one-camera
case. Two thin side slots store the removable battery-cage doors edge-on; the
round top scoops provide pinch access. Their default recesses are 4.6 x 32 mm;
measure the actual doors and tune `BATTERY_DOOR_SLOT_SIZE` before a long print
if that hardware differs.

The TPU lid pad has separate shallow reliefs for the two shutter buttons. An
asymmetric perimeter notch mates with one boss inside the rigid lid, so the pad
cannot seat after a 180-degree rotation with those reliefs over the wrong ends
of the cameras. The rigid lid's hinge then preserves that keyed orientation
relative to the lower tray every time the case closes.

## Suggested printing

- Base, lid, two-piece over-center latches, latch pins, and hinge pin: PETG,
  ASA, nylon, or another impact-tolerant rigid filament; 0.20 mm layers, four
  walls, and 25% or greater infill.
- Lower tray, lid pad, and gasket: TPU 95A, two or three walls, and 15-20%
  infill. The gasket is for dust and splash resistance, not certified
  waterproofing.
- Print the base, tray, lid pad, gasket, and lid in their exported
  orientations. Print all three pin types on their D-shaped flats. Print the
  latch handle and bail with their broad faces on the bed. The latch bores have
  self-supporting teardrop roofs; lightly drill or ream them only if required
  by the printer's horizontal-hole tolerance.
- Print two copies of each of these four files; print every other STL once:

  - `mission1_field_case_over_center_latch_handle_print_two.stl`
  - `mission1_field_case_over_center_latch_bail_print_two.stl`
  - `mission1_field_case_latch_base_pin_print_two.stl`
  - `mission1_field_case_latch_link_pin_print_two.stl`

Printer and filament tolerances vary. Test a camera pocket, battery pocket,
hinge, and latch engagement before relying on the case in the field. Pocket
and pin clearances are constants near the top of the Python generator and can
be tuned without importing or editing an STL.

The default soft-hood relief opens to 55.6 mm and extends 10 mm beyond the
procedural lens face. Those dimensions are based on the supplied case visuals;
measure the particular soft attachment and tune the `LENS_HOOD_*` constants if
its production tolerance differs.

## Multicolor lid

Open `mission1_field_case_ams_project.3mf` for the complete six-plate kit. The
lid is a single compound object with aligned shell, title, and subtitle color
bodies, so an AMS filament can be assigned to each body without repositioning
text. Every lettering island shares a bonding face with the lid. The project
also contains two handles, two bails, two base pins, two link pins, and the
hinge pin on its printed-hardware plate. It uses stock P1S, PETG, and TPU preset
IDs; review the selected presets for the loaded filament before slicing.

Use the AMS for the three-color PETG lid plate. A standard AMS does not feed
TPU reliably, so map the TPU-only plates to the external spool and print those
plates separately.

The three matching STLs remain available for slicers that do not consume 3MF.
Import them together as a single multi-part object without moving them relative
to one another:

- `mission1_field_case_lid.stl`
- `mission1_field_case_lid_title_inlay.stl`
- `mission1_field_case_lid_subtitle_inlay.stl`

Assign a shell color to the lid and separate colors to the title and subtitle.
The inlays are 0.8 mm deep and sit flush in matching recesses. A multi-material
printer can print all three parts together; with a single-material printer,
print the inlays separately and bond them into the recesses.

## Assembly

1. Press the lower TPU tray into the base. Slide the two removable battery-cage
   doors edge-on into the thin outer slots if they are being carried.
2. Seat the TPU gasket in the lid channel. Fit the TPU pad inside the lid with
   its asymmetric notch over the matching boss; it will not sit flat in the
   reverse orientation.
3. Alternate the base and lid hinge knuckles, then slide in the printed hinge
   pin. A 3 mm metal rod may be substituted for a more durable hinge.
4. Put one handle between each pair of supported base ears and insert a base
   pin. The broad lower pull tab faces the case. Place the bail rails outside
   the base ears, align both bail-ear holes with the handle's moving-link hole,
   and insert the link pin. The shallow far-end detents resist pin walkout. M3
   shoulder bolts or smooth 3 mm rod with retainers are the more durable field
   option.
5. With a handle pulled outward, hook its U-shaped bail over the rounded lid
   catch. Swing the lower handle inward against its positive stop. The moving
   link pin briefly aligns with the base pin and catch, adds about 0.18 mm of
   draw, then passes 14.5 degrees over center. Bail tension now holds the handle
   against the stop instead of relying on a flexing snap lip. To release it,
   pull the lower tab outward across center and lift the slack bail off.
6. Load the two cameras into their separate, opposed pockets with the soft lens
   hoods in the flared ends, then place the four batteries terminal-down. The
   keyed lid pad preloads the camera bodies and batteries without pressing the
   shutter buttons.

The dimensions use the local procedural MISSION 1 reference and battery-slot
cross-checks from the existing holder designs linked in the generator's module
documentation. The user-supplied case and Pelican-latch models are functional
and visual precedents only; their meshes are not copied or imported.
