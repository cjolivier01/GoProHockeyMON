# Dual MISSION 1 field case

`mission1_field_case_blender.py` creates every printable part of a
rugged case for two GoPro MISSION 1 cameras and four Enduro 2/HERO13-format
batteries. It reads no STL during generation, and every part fits within a
250 x 250 mm build area. The latch lever and moving hook are derived from the
mechanism in the user-supplied `pelican_case_blender_2.9.blend`; their processed
mesh coordinates are embedded directly in the Python file, so generation does
not load that `.blend` or any STL at runtime.

Build all ten STLs and the multicolor 3MF project with:

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
flare/hood. Four 34.5 x 13.5 mm battery pockets provide 1 mm total clearance
around the 33.5 x 12.5 mm generated inspection batteries and retain their
existing 21.8 mm insertion depth. The batteries are 40.56 mm tall and sit
terminal-down. Two outer 50 x 11 mm door pockets are recessed 11 mm. The
generated 50 x 10 x 18 mm door solids remain 7 mm proud for an easy finger
grip.

Two miscellaneous-storage compartments follow the open side channels in the
supplied `lower_tray.stl` reference. The left compartment runs beside both
opposed cameras and is 37.8 x 118.4 x 31 mm. The right compartment is a
continuous stepped pocket: its 58 x 52.9 mm lower section continues upward as
a narrower 37.9 x 68.5 mm section beside the rear camera. The sections overlap,
and a 2 mm inside fillet rounds the step instead of leaving a TPU tear point.
Both compartments leave 4 mm of TPU beneath their floors and at least 4 mm to
the tray side walls, enlarged battery-door slots, enlarged battery row, and
procedural camera/hood recesses.

The TPU lid pad has separate shutter-button reliefs. Its asymmetric perimeter
notch mates with a rigid lid boss, so the pad seats in only the correct
direction. Two localized 11 mm extensions meet the proud battery doors with
the same 0.6 mm preload as the camera/battery contact face, preventing the
doors from rattling when the case is closed.

With `BUILD_REFERENCE_MOCKUPS = True`, the script also creates four procedural
33.5 x 12.5 x 40.56 mm battery solids and two procedural 50 x 10 x 18 mm door
solids seated in those pockets for visual inspection. They are reference-only
scene objects, not additional STL dependencies or print outputs.

## Lid logo

The only lid text is `GoPro Missions`, set in the compact embedded Neuropol
GoPro-style face. Its minimum stroke is widened from 1.475 mm to 2.2125 mm,
exactly 50% thicker than the original. Four small blocks below it follow the
familiar GoPro layout. All lettering and all four blocks use the same orange
material and are joined into one shallow 0.8 mm raised logo STL.

`mission1_field_case_ams_project.3mf` contains the lid as one aligned two-color
compound object:

- black shell
- orange `GoPro Missions` text and four orange blocks

The lid therefore needs only two AMS filaments. The 3MF declares black and
orange rigid filaments plus orange TPU as filament 3 for the separate TPU
plates; TPU should normally use an external spool.

For another slicer, import these files together without changing their relative
positions:

- `mission1_field_case_lid.stl`
- `mission1_field_case_lid_logo_orange_inlay.stl`

The exported STLs share one assembly print origin: the orange logo occupies the
first 0.8 mm and the black lid begins directly above it. Import them as one
multipart object so the slicer preserves that Z alignment. Every orange island
has a verified bonding face against the uninterrupted black lid surface. The
orange STL retains `_inlay` in its filename for compatibility, although this
revision uses it as a raised logo rather than a recessed inlay.

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

Each latch uses:

- one M3 x 30 ISO 4762 / DIN 912 Allen socket-head cap screw with a maximum
  5.5 mm head diameter and 3.0 mm head height, plus one standard M3 hex nut
  for the case-side fixed pivot; use a 2.5 mm Allen wrench
- one moving-link rod cut to `LATCH_LINK_ROD_LENGTH` (20.48 mm by default)

Two shaped mounting guards are part of the case base. A continuous 3.5 mm bore
through both guards and the source lever is an easy-running clearance for the
M3 fixed-pivot screw. On each latch, the screw head is fully recessed into a
6.0 mm-diameter, 3.2 mm-deep cylindrical counterbore on the case-outside
guard. Its circular region clears the socket head, while a 45-degree roof
closes the horizontal pocket for printing. The 3.0 mm-tall head sits 0.2 mm
below the outside face. A standard nut is fully recessed in a captive 5.8
mm-across-flats by 2.7 mm-deep hex pocket on the guard toward the case center.
The M3 x 30 screw fully engages the 2.4 mm nut thickness, reaches 3.02 mm past
the nut-pocket floor, and projects approximately 0.32 mm beyond the inboard
guard face. The captive pocket extends above the hex with its own 45-degree
printable roof. At the moving pivot, the 4 mm rod passes through the lever's
4.4 mm running bore and is retained by the hook's 3.9 mm bore.

`PIVOT_MIN_WALL_THICKNESS = 2.0` is the shared configurable strength rule for
the case mounts, latch parts, and handle. Each case ear now starts as a gradual
lower web, reaches the boss on a 45-degree printable chord, follows a rounded
upper arc, and curves back into the case wall. There is no horizontal underside
ledge to support. The reinforced ears retain at least 2.22 mm
beside the lower chord and 3.14 mm above the teardrop bore roof.

The lever has dedicated circular reinforcement around its 3.5 mm fixed bore
and 4.4 mm moving-link bore, and
the hook has reinforced outer cheeks around its 3.9 mm bore. These moving-part
bosses provide 2.50 mm nominal radial wall. The closest intentional opening is
the lever snap dimple, which still leaves 2.90 mm between the fixed bore and
air. Matching generated sweep reliefs preserve the complete source toggle path
without thinning either link-pivot ring.

The lid has one continuous 5 mm flared rim with a full 3 mm vertical loaded
edge and 5.4 mm radial thickness. At each latch, a deep bay is cut through the
outer skirt while retaining a 4 mm skirt back wall. A continuous 2.4 mm-thick,
22.4 mm-wide flat load ledge fills the former open space between that wall and
the catch. It overlaps the back wall by 1 mm and reaches 0.4 mm into each side
tower. The 2.6 mm-diameter horizontal capture rail is embedded through the
outer edge of this ledge rather than hanging as a stand-alone cylinder. Its
exposed upper half remains the retention bead. The 4.5 mm-thick side towers
carry both ends, keep the 20.48 mm-wide hook from walking sideways off the
catch, and stand proud of it to deflect impacts.

The source model's obsolete lower jaw has been removed. The moving hook now
has a full-width 3.2 mm reinforced upper arm and a true cylindrical central
boss, 2.8 mm in diameter and 16 mm wide, that enters the recess on the
caseward side of the rail. A second overlapping 3.4 mm-diameter round boss
bonds it deeply into the arm. Below those round retention features is an 18
mm-wide by 1.3 mm-deep flat bearing pad with a 2.8 mm-tall reinforced root.
That pad—not the cylinder—carries the downward clamp load. There is no pointed
nose or thin flexing wedge. After all motion clearances are cut, generation
verifies an intact 2.1 x 15.2 mm core through the catch, an intact 2.7 x 15.2
mm core through its root, an intact 1.6 x 15.2 mm core through their overlap,
and 48.245998 of the intended 48.246000 mm3 flat-pad core. These large
continuous sections are intended to remain sturdy when the hook is printed in
hard TPU.

At the hard lid seat, the flat pad has 0.14 mm clearance above the ledge. The
uncompressed gasket raises the lid 0.25 mm, producing 0.11 mm of flat-surface
preload. The round retention boss remains 0.25 mm above the ledge and the
larger root clears even the uncompressed ledge by 0.05 mm, so neither round
feature substitutes line contact for the requested flat downward-bearing
surface. The cylindrical boss still blocks outward peel behind the exposed
rail bead.

The rail has 0.10 mm running clearance along its generated release path. The
Python generator samples the actual two-pivot linkage and cuts that path in the
hook's moving frame. During the first 12 degrees of deliberate lever travel,
the upper arm moves outward while the flat pad and round boss remain captured.
The deeper external bay preserves the rigid 4 mm lid back wall while giving
the hook room to move during release. At 24 degrees the pad, root, and boss all
lift clear of the continuous ledge, so the ledge needs no weakening release
scallop. There is no disconnected tooth or lower jaw to print.

Matching 6 mm-thick impact cheeks are integrated into the base on both sides
of each lever. They stand forward of the closed lever, join the shell on
45-degree support-free lower ramps, and use chamfered top returns instead of
brittle square-ended posts. The added thickness fully encloses the fixed-pivot
screw head and nut while preserving the original lever-facing surfaces and
0.2 mm lever clearance on both sides. Together with the lid towers, they
protect the closed hardware from side hits and snags while leaving the full
center finger corridor open. The horizontal catch rail is the only short
bridge that may benefit from tuned bridging or localized support. The load
ledge turns that bridge into an 8.6 mm-deep structural shelf tied into the lid
wall and towers; the guard ramps themselves do not require support in the
exported orientation, and the captive nut pockets close with 45-degree roofs.

The uncompressed lid begins 0.25 mm above its hard seated position. Pressing
the broad lever inward places its flat pad against the load ledge, draws the
lid down onto the gasket, and passes the linkage over center. The generated
geometry verifies zero hard-seated hook/lid intersection, 1.246471 mm3 minimum
total capture and 0.228854 mm3 of flat-pad capture during an attempted 0.15 mm
lid lift, 6.656732 mm3 total preload and 2.516820 mm3 of isolated flat-pad
preload at the full 0.25 mm uncompressed gasket position, and 31.467644 mm3
minimum engagement during a 0.60 mm outward-peel attempt. It also verifies
1.399353 mm3 minimum capture at 12 degrees open and complete rail/ledge release
at 24 degrees. The complete coupled opening path has zero hook/base, hook/lid,
and lever/hook collision.

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
2. From the case-outside guard, insert an M3 x 30 ISO 4762 / DIN 912 Allen
   socket-head cap screw through the first guard, the lever's 3.5 mm
   easy-running bore, and the case-center guard. Seat a standard M3 nut fully
   in its captive inside hex recess and tighten with a 2.5 mm Allen wrench only
   until axial play is removed; the lever must still pivot freely.
3. Nest the hook around the lever's moving end, align the link holes, and press
   the rod cut to `LATCH_LINK_ROD_LENGTH` through the hook and lever until its
   ends are flush.
4. Close the lid and lift the broad lever far enough to place the hook's round
   central boss in the molded recess behind the horizontal lid rail, between
   the two protective towers. Press the broad outer lever inward until the
   hidden detent snaps closed. Confirm that the upper arm is centered between
   the towers, its flat pad is over the load ledge, and the boss is behind the
   rail rather than perched on its outside face. Pull the broad lever outward
   through the detent to unload the gasket; the linkage then lifts both pad and
   boss clear of the continuous ledge and rail so the lid can open.

Deburr and lightly chamfer moving-link rod ends. Do not hammer a rod into an
unsupported hook cheek. Printer shrinkage varies, so print one lever and hook
first and test the M3 screw clearance and moving-link rod fits before
committing the full shell.

## Separate pivoting handle

`mission1_field_case_pivoting_handle_bar.stl` is the only separate handle
print. It is a U-shaped bar with five reference-style grip holes. Its two
fixed mounting lugs are generated directly into the case base and sit inside
relieved forks in the moving handle arms, so the base itself needs no mounting
screws and neither lug intrudes into the finger opening. Like the latch ears,
the lugs rise on printable lower webs and use curved upper returns rather than
sharp projecting corners.

Install the handle with one M3 x 12 ISO 4762 / DIN 912 Allen socket-head cap
screw and one standard M3 hex nut per side. Each screw enters from the
case-outside face of its handle fork, passes through the handle's continuous
3.5 mm easy-running path and the existing base lug, and seats in the captive
nut on the case-center face. The base is unchanged: both integrated mounting
lugs retain their existing 3.9 mm bores, which already provide free travel for
an M3 screw.

Each 5.5 mm-maximum-diameter by 3.0 mm-tall socket head is fully recessed in a
6.0 mm-diameter by 3.2 mm-deep cylindrical counterbore with a printable
45-degree roof; use a 2.5 mm Allen wrench. The matching standard nut is fully
recessed in a 5.8 mm-across-flats by 2.7 mm-deep support-free hex pocket. The
locally thickened fork ends retain a complete 1.0 mm floor between each recess
and the fixed-lug sweep cavity. An M3 x 12 screw fully engages the 2.4 mm nut,
reaches 4.2 mm past the nut-pocket floor, and projects 1.5 mm beyond the
inboard handle face.

The handle pivot is centered horizontally and vertically on the assembled case
front: X = 0 and Z = 36.5 mm. The 95 mm-wide folded bar occupies only the
reserved center zone. The two exact latches retain their compatible X = ±82 mm
centerlines; their
moving levers remain 22.16 mm from the handle's full folded and swinging X
envelope. The 6 mm integrated guards retain 15.96 mm from that envelope, and
the installed latch M3 screw tips retain 15.64 mm. The two old
front-center impact ribs are deliberately omitted so this entire access path
stays open. When raised, the smaller 32.5 mm-drop handle leaves 28.1
mm between the case face and the inside of the grip across the unobstructed 75
mm opening. Around each fixed lug, the socket-head fork cheek is 4.2 mm thick
and the captive-nut cheek is 3.7 mm thick. The support-free outer pivot profile
retains at least 1.31 mm around the large counterbore's lower chord and 1.86 mm
above its printable roof; the central M3 shaft path retains 2.56 mm at the
lower chord.
The generator rejects less than 25 mm of raised finger clearance, less than
75 mm of unobstructed grip width, less than 22 mm of moving-latch finger-access
clearance, less than 15.5 mm between the handle and integrated latch guards, or
less than 15 mm between the handle and installed M3 screw tips.

## Hinge clearances

The alternating base and lid knuckles have matching cylindrical swing pockets
cut through the otherwise continuous rear rims. These pockets prevent the lid
flange from striking the base knuckles and prevent the lid knuckles from
striking the base wall. The generated base and lid have been checked through a
0-110 degree opening sweep without rigid intersection. Do not fill these rear
reliefs when adding manual supports.

Each of the three base knuckles now has a full-width tapered web beneath its
barrel. The web begins 0.3 mm inside the rear case wall, rises outward at 45
degrees, and joins the 10 mm barrel at its lower-outboard tangent. This removes
the unsupported lower circular arc and gives the barrel a much larger load path
into the shell without changing the hinge axis, alternating axial clearances,
or internal case dimensions. Its original hinge path is enlarged only to a 4.5
mm bore so the requested 4.1 mm bar can pass through all three base knuckles.
Print the base upright as exported; the hinge webs are designed not to require
support.

The lid barrels are fused into the complete flared rim before their 4.8 mm
round receivers are opened through the rear/outboard side by 4.6 mm slots.
Each slot is parallel to the lid plate. The installed slots therefore face
rearward and cannot lift off the bar while the lid is closed. The unchanged
base remains in the true slot-aligned escape path through 65 degrees open; at
70 degrees the complete lid can slide diagonally up and forward from the bar.
The 0.5 mm slot clearance gives a nominal 4.1 mm bar cleanup allowance after
support removal, while the 10 mm outside diameter retains 2.6 mm of radial
barrel wall.

Generation checks 224 slot-aligned path positions from 0 through 65 degrees
and verifies at least 0.687230 mm3 of blocking intersection at every sampled
angle. At 70 degrees it checks 17 travel positions with the complete 151 mm
rod centered and within 0.05 mm of both axial-play extremes: all 51 full-rod
samples and all base/lid samples clear. It also checks each finished receiver,
the continuous seated rod path, and a 1-degree base/lid rotation sweep from 0
through 110 degrees.

Two 6 mm-diameter by 3 mm-long solid bosses are part of the lid just outside
the outer faces of the base's end knuckles. The straight rod is cut to 151 mm,
placing each end 0.5 mm inside its base-knuckle face. Each lid stop begins 0.3
mm beyond that face, leaving 0.8 mm clearance at each rod end and 1.6 mm total
axial play. The stops therefore pass outside the rod during 70-degree slide-on
assembly, then prevent it from walking out in either direction while the lid
is attached. Their smaller diameter clears the unchanged base rear wall;
generated solid probes and deliberate axial-overtravel probes verify both
stops and retention.

## Suggested printing

- Base, lid, broad latch levers, handle bar, and hinge pin: PETG, ASA, nylon,
  or another impact-tolerant rigid filament; 0.20 mm layers, four walls, and at
  least 25% infill.
- The upper moving latch hooks may be printed in hard TPU. Use the stiffest TPU
  your printer handles reliably, at least five walls, and high infill around
  the flat bearing pad, round retention boss, and link-pivot end. Soft 95A
  tray-style settings are not recommended for this load-bearing part.
- Lower tray, lid pad, and gasket: TPU 95A, two or three walls, and 15-20%
  infill. The gasket is for dust and splash resistance, not certified
  waterproofing.
- Print the base, lid, tray, lid pad, gasket, latches, and handle bar in their
  exported orientations. Their broad faces are already on the bed.
- The case-side latch and handle mounts rise on 45-degree lower webs and do not
  require support. Do not place support inside their teardrop pivot bores.
- The two lid hinge slots bridge the full 22.8 mm receiver widths in the broad-
  face-down lid orientation. Add removable support in those two slots, then
  remove it completely and verify the 4.1 mm bar slides through the 4.6 mm
  openings without resistance before assembly.
- Print the optional headless 4.1 mm hinge pin on its D-shaped flat, or cut a
  4.1 mm metal bar to 151 mm. Verify the actual bar against a small bore test
  before printing the full base.

Test camera, battery, latch, handle, and hinge fits before field use. Pocket,
pivot, and press-fit dimensions are constants near the top of the Python file
and can be regenerated without editing an STL.

## Case assembly

1. Press the lower TPU tray into the base and lay the two removable battery
   doors in the shallow outer pockets if carried; each door remains 7 mm proud.
2. Seat the TPU gasket in the lid channel. Fit the TPU pad with its asymmetric
   notch over the matching rigid boss.
3. Feed and center the 151 mm-long, 4.1 mm bar (or headless printed D-profile
   pin) through the three base knuckles, leaving both ends about 0.5 mm inset.
   Hold the lid approximately 70 degrees open. Align both rearward-opening
   receivers with the installed bar and slide the lid diagonally down and rear
   along the slot direction, then rotate it closed. The unchanged base
   blocks that same removal path through 65 degrees, while the two solid lid
   stops retain the bar axially.
4. Install each latch with one M3 x 30 ISO 4762 / DIN 912 Allen socket-head cap
   screw, one standard M3 nut, and a moving-link rod cut to
   `LATCH_LINK_ROD_LENGTH`. Install the separate handle bar with two M3 x 12
   Allen socket-head screws and two standard M3 nuts, one set per side.
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
