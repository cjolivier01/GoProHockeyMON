# Dual MISSION 1 field case

`mission1_field_case_blender.py` creates every printable part of a
rugged case for two GoPro MISSION 1 cameras and four Enduro 2/HERO13-format
batteries. It reads no STL during generation, and every part fits within a
250 x 250 mm build area. The latch lever and moving hook are derived from the
mechanism in the user-supplied `pelican_case_blender_2.9.blend`; their processed
mesh coordinates are embedded directly in the Python file, so generation does
not load that `.blend` or any STL at runtime.

Build all thirteen STLs and the multicolor 3MF project with:

```sh
make -C cooler-gopro mission1-field-case
```

The Makefile requires GNU Make 4.3 or newer. On macOS, install a current GNU
Make and run the command as `gmake` when the system `make` is BSD Make.

The lower insert is one flush-top TPU tray. In the assembled Blender scene its
bottom is positioned at Z = 3.2 mm, directly on top of the rigid case floor;
it does not share the floor's Z = 0-3.2 mm volume. The standalone STL and 3MF
plate normalize the tray back to Z = 0 for printing. It has two independent
camera pockets cut from the local procedural MISSION 1 body, including its
offset lens housing, controls, and rounded body. The cameras face opposite
directions so their lens lobes nest while a continuous TPU web keeps the
pockets separate.
Each lens end widens into a trapezoidal relief for the soft MISSION 1 Pro lens
flare/hood. Four exact 33.5 x 12.5 mm battery pockets retain their existing
21.8 mm insertion depth; the generated inspection batteries are 40.56 mm tall
and sit terminal-down. Two outer 50 x 10 mm door pockets are recessed 10 mm.
The generated 18 mm-tall door solids remain 8 mm proud for an easy finger grip.

Two miscellaneous-storage compartments follow the open side channels in the
supplied `lower_tray.stl` reference. The left compartment runs beside both
opposed cameras and is 37.8 x 119 x 31 mm. The right compartment runs up to
the flared lens-hood clearance and is 58.4 x 53.5 x 31 mm. Both leave 4 mm of
TPU beneath their floors and at least 4 mm to the tray side walls,
battery-door slots, battery row, and procedural camera/hood recesses.

The TPU lid pad has separate shutter-button reliefs. Its asymmetric perimeter
notch mates with a rigid lid boss, so the pad seats in only the correct
direction. Two localized 11 mm extensions meet the proud battery doors with
the same 0.6 mm preload as the camera/battery contact face, preventing the
doors from rattling when the case is closed.

With `BUILD_REFERENCE_MOCKUPS = True`, the script also creates four procedural
40.56 mm battery solids and two procedural 50 x 10 x 18 mm door solids seated
in those pockets for visual inspection. They are reference-only scene objects,
not additional STL dependencies or print outputs.

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

Each clasp uses the two moving bodies extracted from the supplied Pelican case
scene: the broad outer lever and its curved moving hook. They are separate,
manifold prints rather than a print-in-place substitute. The visible source
surfaces are retained at 80% scale; the two pin bores and hidden overlapping
interior surfaces were adapted so the visualization geometry can articulate as
a printable mechanism.

Print two copies of:

- `mission1_field_case_pelican_latch_lever_print_two.stl`
- `mission1_field_case_pelican_latch_hook_print_two.stl`

Each latch uses two nominal 4 mm stainless rods:

- one fixed-pivot rod cut to `LATCH_FIXED_ROD_LENGTH` (28.88 mm by default)
- one moving-link rod cut to `LATCH_LINK_ROD_LENGTH` (20.48 mm by default)

Two shaped mounting ears are part of the case base. Their 3.9 mm retaining
bores grip the fixed rod while the source lever's 4.4 mm bore turns freely on
it. At the moving pivot, the rod passes through the lever's second 4.4 mm
running bore and is retained by the hook's 3.9 mm bore. The exposed circular
ends in the assembled view are the requested stainless rods, not printed latch
features.

`PIVOT_MIN_WALL_THICKNESS = 2.0` is the shared configurable strength rule for
the case mounts, latch parts, and handle. Each case ear now starts as a gradual
lower web, reaches the boss on a 45-degree printable chord, follows a rounded
upper arc, and curves back into the case wall. There is no horizontal underside
ledge to support. The reinforced ears retain at least 2.22 mm
beside the lower chord and 3.14 mm above the teardrop bore roof.

The lever has dedicated circular reinforcement around both 4.4 mm bores, and
the hook has reinforced outer cheeks around its 3.9 mm bore. These moving-part
bosses provide 2.50 mm nominal radial wall. The closest intentional opening is
the lever snap dimple, which still leaves 2.45 mm between the fixed bore and
air. Matching generated sweep reliefs preserve the complete source toggle path
without thinning either link-pivot ring.

The lid has one continuous 5 mm flared rim with a full 3 mm vertical loaded
edge and 5.4 mm radial thickness. At each latch, a deep bay is cut through the
outer skirt while retaining a 4 mm skirt back wall. A 2.6 mm-diameter
horizontal capture rail spans that bay and is bonded to the back wall by a 1.2
mm web. Reinforced, support-free side towers carry the rail ends and guide the
20.48 mm-wide hook so it cannot walk sideways off the catch.

The moving hook has a round-ended throat with 0.1 mm radial running clearance
and 2 mm of surrounding wall. Its clearance channel is not an arbitrary
straight slot: the Python generator samples the real two-pivot linkage and
cuts the curved path traced by the fixed lid rail in the hook's local frame.
When closed, the rail sits at the deep end of the throat with the hook wrapped
around it. Opening the lever translates the hook along that path; it remains
captured through 12 degrees of lever travel and clears the rail by 24 degrees.

The uncompressed lid begins 0.25 mm above its hard seated position. Pressing
the broad lever inward pulls the hook's throat onto the horizontal rail, draws
the lid down onto the gasket, and passes the linkage over center. The generated
geometry verifies zero hard-seated hook/lid intersection, at least 0.97 mm3 of
engagement during an attempted 0.15 mm lid lift, and at least 4.25 mm3 of rail
preload at the full 0.25 mm uncompressed gasket position. The complete coupled
opening path is also checked for zero hook/base, hook/lid, and lever/hook
collision.

The source toggle's natural over-center travel is retained. Opposed hidden
spherical snap detents in both base ears center the lever and prevent normal
pivot play from bypassing the snap. The ear spacing leaves 0.2 mm axial
clearance per side, while the larger opposed dimples clear both worst-case
axial positions at the fully seated pose. A dedicated quarter-degree exact
sweep at -0.2, 0, and +0.2 mm verifies zero closed contact, at least 0.0560 mm3
of peak release engagement everywhere in that range, and complete release by
22 degrees open. Pushing the lever in the wrong direction is stopped by the
base across the same axial range.

To install one latch:

1. Place the lever between the two integrated base ears and align the fixed
   pivot holes.
2. Support both ears and press the rod cut to `LATCH_FIXED_ROD_LENGTH` through
   the first ear, lever, and second ear until centered.
3. Nest the hook around the lever's moving end, align the link holes, and press
   the rod cut to `LATCH_LINK_ROD_LENGTH` through the hook and lever until its
   ends are flush.
4. Close the lid, lift the broad lever far enough that the open end of the
   moving hook's curved throat can pass over the horizontal lid rail, and seat
   the rail in that throat. Press the broad outer lever inward until the hidden
   detent snaps closed. The rail must be visibly seated at the round, deep end
   of the hook throat. Pull the broad lever outward through the detent to unload
   the gasket; the linkage then translates the throat off the rail so the lid
   can open.

Deburr and lightly chamfer rod ends. Do not hammer a rod into an unsupported
ear or hook cheek. Printer shrinkage varies, so print one lever and hook first
and test both fits with the actual rod before committing the full shell.

## Separate pivoting handle

`mission1_field_case_pivoting_handle_bar.stl` is the only separate handle
print. It is a U-shaped bar with five reference-style grip holes. Its two
fixed mounting lugs are generated directly into the case base and sit inside
relieved forks in the moving handle arms, so the base itself needs no mounting
screws and neither lug intrudes into the finger opening. Like the latch ears,
the lugs rise on printable lower webs and use curved upper returns rather than
sharp projecting corners.

The default `HANDLE_HARDWARE_MODE = "ROD"` uses two 12 mm lengths of 4 mm rod.
Each integrated lug has a 3.9 mm retaining bore and each moving handle arm has
a 4.4 mm running bore. Press a rod through the outer fork cheek, the fixed lug,
and the inner fork cheek.

For M4 hardware, set `HANDLE_HARDWARE_MODE = "M4"` and regenerate every STL.
That changes the integrated lug bores to 4.4 mm. Use two M4 x 20 screws with
washers and locknuts; those screws are only pivots, not base-mounting hardware.

The handle pivot is centered horizontally and vertically on the assembled case
front: X = 0 and Z = 36.5 mm. The 95 mm-wide folded bar occupies only the
reserved center zone. The two exact latches retain their compatible X = ±82 mm
centerlines; their
moving levers remain 24.26 mm from the handle's full folded and swinging X
envelope, while the integrated mounts retain 20.06 mm clearance. The two old
front-center impact ribs are deliberately omitted so this entire access path
stays open. When raised, the smaller 32.5 mm-drop handle leaves 28.1
mm between the case face and the inside of the grip across the unobstructed 75
mm opening. Each fork cheek is 2.10 mm thick, while the support-free outer
pivot profile leaves at least 2.11 mm beside its lower chord and 2.99 mm above
the teardrop running bore.
The generator rejects less than 25 mm of raised finger clearance, less than
75 mm of unobstructed grip width, less than 24 mm of moving-latch finger-access
clearance, or less than 20 mm between the handle and integrated latch mounts.

## Hinge clearances

The alternating base and lid knuckles have matching cylindrical swing pockets
cut through the otherwise continuous rear rims. These pockets prevent the lid
flange from striking the base knuckles and prevent the lid knuckles from
striking the base wall. The generated base and lid have been checked through a
0-110 degree opening sweep without rigid intersection. Do not fill these rear
reliefs when adding manual supports.

## Suggested printing

- Base, lid, latch levers and hooks, handle bar, and hinge pin: PETG, ASA,
  nylon, or another impact-tolerant rigid filament; 0.20 mm layers, four walls,
  and at least 25% infill.
- Lower tray, lid pad, and gasket: TPU 95A, two or three walls, and 15-20%
  infill. The gasket is for dust and splash resistance, not certified
  waterproofing.
- Print the base, lid, tray, lid pad, gasket, latches, and handle bar in their
  exported orientations. Their broad faces are already on the bed.
- The case-side latch and handle mounts rise on 45-degree lower webs and do not
  require support. Do not place support inside their teardrop pivot bores.
- Print the hinge pin on its D-shaped flat. A 3 mm metal rod can replace it.

Test camera, battery, latch, handle, and hinge fits before field use. Pocket,
pivot, and press-fit dimensions are constants near the top of the Python file
and can be regenerated without editing an STL.

## Case assembly

1. Press the lower TPU tray into the base and lay the two removable battery
   doors in the shallow outer pockets if carried; each door remains 8 mm proud.
2. Seat the TPU gasket in the lid channel. Fit the TPU pad with its asymmetric
   notch over the matching rigid boss.
3. Alternate the base and lid hinge knuckles, then insert the printed hinge pin
   or a 3 mm metal rod.
4. Install each latch with rods cut to `LATCH_FIXED_ROD_LENGTH` and
   `LATCH_LINK_ROD_LENGTH`, then install the separate handle bar with two 12 mm
   lengths of 4 mm rod by default or with regenerated M4 hardware.
5. Load the two opposed cameras with their soft lens hoods in the flared ends,
   then load four batteries terminal-down.

## Reference acknowledgments

The latch bodies come from the user-supplied
`pelican_case_blender_2.9.blend`. The local file is a source reference only;
the generator embeds the processed coordinates needed for its two latch STLs
and has no runtime dependency on the file. The handle meshes were used only as
visual and functional references; the handle remains independent parametric
geometry:

- “Suitcase/Box/Case Handle” by Thingiverse user `henryarnold`:
  <https://www.thingiverse.com/thing:2926036>
- The handle package also acknowledges its upstream design:
  <https://www.thingiverse.com/thing:299982>

The local reference packages state Creative Commons Attribution but do not
identify a version. The GoPro name and logo are separate trademarks.
