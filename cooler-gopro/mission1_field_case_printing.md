# Dual MISSION 1 field case

`mission1_field_case_blender.py` creates every printable part of a
rugged case for two GoPro MISSION 1 cameras and four Enduro 2/HERO13-format
batteries. It reads no STL during generation, and every part fits within a
250 x 250 mm build area. The repaired coordinates of the CC BY Pelican latch
reference are embedded directly in the Python file so its output matches the
supplied latch without a runtime file dependency.

Build all twelve STLs and the multicolor 3MF project with:

```sh
make -C cooler-gopro mission1-field-case
```

The Makefile requires GNU Make 4.3 or newer. On macOS, install a current GNU
Make and run the command as `gmake` when the system `make` is BSD Make.

The lower insert is one flush-top TPU tray. It has two independent camera
pockets cut from the local procedural MISSION 1 body, including its offset lens
housing, controls, and rounded body. The cameras face opposite directions so
their lens lobes nest while a continuous TPU web keeps the pockets separate.
Each lens end widens into a trapezoidal relief for the soft MISSION 1 Pro lens
flare/hood. Four batteries sit terminal-down, and two thin outer slots store
the removable battery-cage doors edge-on.

The TPU lid pad has separate shutter-button reliefs. Its asymmetric perimeter
notch mates with a rigid lid boss, so the pad seats in only the correct
direction.

## Lid logo

The only lid text is `GoPro Missions`, set in a large embedded Neuropol glyph
subset. Four small blocks below it follow the GoPro mark: dark blue, blue,
cyan, and white. The text and last block share one white inlay STL, while the
other three blocks have their own color bodies.

The embedded Neuropol 3.100 glyph subset is from Ray Larabie's CC0 release. It
keeps Blender CLI and Text Editor generation self-contained; no system font is
needed.

`mission1_field_case_ams_project.3mf` contains the lid as one aligned five-color
compound object:

- black shell
- white `GoPro Missions` text and white block
- dark-blue block
- blue block
- cyan block

The 3MF declares those five rigid filaments plus TPU as filament 6. Five rigid
colors require more than one four-slot AMS, a tool-changing system, or planned
manual color swaps. TPU remains on separate plates and should normally use an
external spool.

For another slicer, import these files together without changing their relative
positions:

- `mission1_field_case_lid.stl`
- `mission1_field_case_lid_logo_white_inlay.stl`
- `mission1_field_case_lid_logo_dark_blue_inlay.stl`
- `mission1_field_case_lid_logo_blue_inlay.stl`
- `mission1_field_case_lid_logo_cyan_inlay.stl`

The 0.8 mm inlays have exact shared boundaries with the shell for compound
multicolor slicing and every island shares a verified bonding face. Standalone
inlay installation may require light sanding because no assembly gap is added
to the multicolor interface.

## Pelican toggle latches

Each clasp is the supplied Pelican-catch geometry: a broad outer U lever, its
nested hooked link, and the original captive link pin. The three shells print
in place as one moving mechanism. The generator embeds repaired coordinates
from the reference, scales them uniformly so the existing fixed bore is 4.4 mm,
and adds no cylinders, barrels, or other geometry to the latch silhouette.

Print two copies of:

- `mission1_field_case_exact_pelican_latch_print_two.stl`

Each latch uses one 36 mm length of nominal 4 mm stainless rod. The single
integrated center tongue on the case has a 3.9 mm press-fit bore. The rod then
passes through the latch's original fixed pivot, which scales to a 4.4 mm
running bore. The fixed pivot bosses remain inside the reference's side cheeks;
there are no outside mounting ears or transverse printed barrels.

The lid now has one integrated keeper ramp at each latch location. Its dense
bearing arc comes from a conservative full-width projection of the exact
hooked link, including its side bevels. At nominal closure the arc supplies
0.25 mm of gasket draw; after that take-up, the rigid profiles clear by about
0.0014 mm instead of jamming on coarse straight chords. Pressing the broad
lever inward wedges the moving link against the ramp and carries the linkage
over center. An upward lid load then bears directly from the keeper into that
link, through the two latch pivots, and into the base's 4 mm mounting rod. The
linkage must pass back across center before the lid can rise, so no separate
lid-side catch needs to be printed or installed.

To install one latch:

1. Work the printed-in-place center link through its full travel and clear any
   strings without cutting the captive internal pin.
2. Slide the case's center tongue into the rear channel of the latch and align
   its 3.9 mm hole with the latch's 4.4 mm fixed-pivot bore.
3. Support the tongue and press the 36 mm rod through the latch and tongue.
4. Close the lid, place the moving head over its localized keeper ramp, and
   press the broad outer lever inward until the linkage passes over center.
   Pull that same broad lever outward to unload the ramp and release it.

Deburr and lightly chamfer rod ends. Do not hammer a rod into an unsupported
tongue. Printer shrinkage varies, so print one latch first and test it with the
actual rod before committing the full shell.

## Separate pivoting handle

`mission1_field_case_pivoting_handle_bar.stl` is the only separate handle
print. It is a U-shaped bar with five reference-style grip holes. Its two
compact fixed mounting lugs are generated directly into the case base and sit
inside relieved forks in the moving handle arms, so the base itself needs no
mounting screws and neither lug intrudes into the finger opening.

The default `HANDLE_HARDWARE_MODE = "ROD"` uses two 12 mm lengths of 4 mm rod.
Each integrated lug has a 3.9 mm retaining bore and each moving handle arm has
a 4.4 mm running bore. Press a rod through the outer fork cheek, the fixed lug,
and the inner fork cheek.

For M4 hardware, set `HANDLE_HARDWARE_MODE = "M4"` and regenerate every STL.
That changes the integrated lug bores to 4.4 mm. Use two M4 x 20 screws with
washers and locknuts; those screws are only pivots, not base-mounting hardware.

The handle pivot is centered horizontally and vertically on the assembled case
front: X = 0 and Z = 36.5 mm. The 94 mm-wide folded bar occupies only the
reserved center zone. The two exact latches sit outboard at X = ±72.5 mm; their
inner edges remain more than 8.5 mm from the handle's full folded and swinging X
envelope. When raised, the smaller 32.5 mm-drop handle leaves 27.5 mm between
the case face and the inside of the grip across the unobstructed 76 mm opening.
The generator rejects less than 25 mm of raised finger clearance, less than
75 mm of unobstructed grip width, or less than 8 mm of latch finger-access
clearance.

## Suggested printing

- Base, lid, print-in-place latches, handle bar, and hinge pin: PETG, ASA,
  nylon, or another impact-tolerant rigid filament; 0.20 mm layers, four walls,
  and at least 25% infill.
- Lower tray, lid pad, and gasket: TPU 95A, two or three walls, and 15-20%
  infill. The gasket is for dust and splash resistance, not certified
  waterproofing.
- Print the base, lid, tray, lid pad, gasket, latches, and handle bar in their
  exported orientations. Their broad faces are already on the bed.
- Print the hinge pin on its D-shaped flat. A 3 mm metal rod can replace it.

Test camera, battery, latch, handle, and hinge fits before field use. Pocket,
pivot, and press-fit dimensions are constants near the top of the Python file
and can be regenerated without editing an STL.

## Case assembly

1. Press the lower TPU tray into the base and load the two removable battery
   doors into the thin outer slots if carried.
2. Seat the TPU gasket in the lid channel. Fit the TPU pad with its asymmetric
   notch over the matching rigid boss.
3. Alternate the base and lid hinge knuckles, then insert the printed hinge pin
   or a 3 mm metal rod.
4. Install each latch with one 36 mm length of 4 mm rod, then install the
   separate handle bar with two 12 mm lengths of 4 mm rod by default or with
   regenerated M4 hardware.
5. Load the two opposed cameras with their soft lens hoods in the flared ends,
   then load four batteries terminal-down.

## Reference acknowledgments

The Pelican latch is redistributed as repaired, compressed coordinate data
under its stated Creative Commons Attribution license. The handle meshes were
used only as visual and functional references; the handle remains independent
parametric geometry:

- “Pelican 1550 Catch Remix” by Thingiverse user `mutedmouse`:
  <https://www.thingiverse.com/thing:4775467>
- “Suitcase/Box/Case Handle” by Thingiverse user `henryarnold`:
  <https://www.thingiverse.com/thing:2926036>
- The handle package also acknowledges its upstream design:
  <https://www.thingiverse.com/thing:299982>

The local reference packages state Creative Commons Attribution but do not
identify a version. The GoPro name and logo are separate trademarks.
