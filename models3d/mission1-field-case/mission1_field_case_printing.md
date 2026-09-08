# Dual MISSION 1 field case

`mission1_field_case_blender.py` creates every printable part of a
rugged case for two GoPro MISSION 1 cameras, four Enduro 2/HERO13-format
batteries, and the assembled parametric dual-fan holder with two installed
80 x 80 x 25 mm nominal fans whose front/rear Noctua pads produce a 27 mm
installed thickness. It reads no STL during generation, and every part fits
within a 250 x 250 mm build area. The rigid shell is 234 x 158 x 97.8 mm;
its largest print-bed footprints are the 244 x 187.8 mm lid and the
241.6 x 187.8 mm base. The latch lever and moving hook are derived from the
mechanism in the user-supplied `pelican_case_blender_2.9.blend`; their processed
mesh coordinates are embedded directly in the Python file, so generation does
not load that `.blend` or any STL at runtime.

Build the eleven-part default kit, four optional loadout/calibration STLs, and
the multicolor 3MF project with:

```sh
make -C models3d mission1-field-case
```

The Makefile requires GNU Make 4.3 or newer. On macOS, install a current GNU
Make and run the command as `gmake` when the system `make` is BSD Make.

The documentation renderings can be regenerated from the same validated model
and exact reference assembly with:

```sh
blender --background --factory-startup \
  --python models3d/mission1-field-case/render_mission1_field_case_previews.py
```

This writes loaded and exploded views of both storage configurations, TPU
snap-hinge and calibration-coupon close-ups, and the closed latch-protector PNG
under `models3d/mission1-field-case/renderings/`. The steep default loaded view
keeps the complete printable base protectors visible while looking down into
the tray pass-through. The closed view shows the unsectioned base and lid
protector walls with both installed latches.

## Stacked TPU storage tiers

The lower insert is now
`mission1_field_case_lower_fan_cradle_tpu.stl`, a 224 x 148 x 6 mm TPU
locator. In the assembled Blender scene its bottom is at Z = 3.2 mm, directly
on top of the rigid case floor; its standalone STL and 3MF plate are normalized
back to Z = 0 for printing. A 214.5 x 131.71 x 3 mm shallow pocket locates the
dual-fan holder's shared rear-grille contact plane while retaining a 3 mm TPU
floor and at least 4.75 mm of TPU at the nearest cradle edge.

The stored default dual-fan assembly is 212.5 x 129.71 x 95.57 mm including
the holder, attached three-prong GoPro adapter, and installed fans. Place the
complete assembly rear-grille-down, with its adapter projecting toward the
front/latch side of the case. The two grille/frame contact regions seat in the
shallow pocket. The padded 80 mm fan bodies end at approximately Z = 36.7 mm,
while only the routed support arm and attached adapter continue upward. This
matches the holder's supported print orientation and avoids a deep negative
mold around the adapter. The complete assembly reaches approximately
Z = 101.77 mm.

`mission1_field_case_upper_equipment_tray_tpu.stl` is the removable
223 x 147 x 35 mm upper tier. Its assembled bottom is at Z = 39 mm on two
rigid side rails, 2.3 mm above the padded installed fan bodies. A localized
rounded 39.5 x 47.5 mm opening lets the routed arm pass through the tray; the
matching opening in the inverted TPU lid pad lets the arm occupy
otherwise-unused tray and pad height while preserving 3.03 mm clearance from
the rigid lid plate.
The tray has 1 mm clearance per side, twice the original clearance, to reduce
friction against the shell. Two 18 x 18 mm scallops open through its front edge
for a direct two-finger lift. Two symmetric 45 x 54 x 32 mm general-purpose
pockets use the otherwise empty rear-left and rear-right strips beside the
camera pair. Each has a 3 mm TPU floor, at least 4.6 mm of TPU beside the
flared lens-hood reliefs, and at least 5 mm to the outer side edge.

The padded fan-body depth is derived from the dual-fan generator's current
nominal fan depth plus the 2 mm storage allowance for the Noctua pads. The
upper-tray elevation rounds up to the next 0.5 mm and the shell height follows
it, preserving the configured 2 mm minimum fan-body clearance when the nominal
depth changes. Plan dimensions and the localized arm opening remain bounded
case-design constraints; incompatible fan counts, sizes, rotations, or
routed-arm geometry are rejected by validation rather than silently producing
an oversized part.
The production Make target constructs the current generated holder, adapter,
and padded fan references and requires zero exact collision with the base,
cradle, upper tray, and inverted lid pad before exporting the printable parts.

The upper tray retains two independent camera pockets cut from the local
procedural MISSION 1 body, including its offset lens housing, controls, and
rounded body. The cameras face opposite directions so their lens lobes nest
while a continuous TPU web keeps the pockets separate; the pair is shifted
rearward around the arm opening.
Each lens end widens into a trapezoidal relief for the soft MISSION 1 Pro lens
flare/hood. Four 34.5 x 13.5 mm battery pockets provide 1 mm total clearance
around the 33.5 x 12.5 mm generated inspection batteries and retain their
existing 21.8 mm insertion depth. The batteries are split into left and right
front banks around the pass-through; they are 40.56 mm tall and sit
terminal-down. Two 50 x 11 mm door pockets occupy the outer side channels and
are recessed 11 mm. The generated 50 x 10 x 18 mm door solids remain 7 mm
proud for an easy finger grip. The two open side pockets remain available for
cables, fasteners, or other small accessories that fit their 32 mm depth.

The TPU lid pad has separate shutter-button reliefs. It also mirrors the upper
tray's two trapezoidal MISSION 1 Pro lens-hood footprints as 2 mm-deep
indentations in its camera-contact face, so the flared soft lens hoods are not
pinched between the two TPU halves. Solid 10.4 mm TPU floors remain beneath
both pockets. A mirrored full-depth arm opening aligns with the tray opening
when the lid closes. The pad's asymmetric perimeter notch mates with a rigid
lid boss, so it seats in only the correct direction. Two localized 11 mm
extensions meet the proud battery doors with the same 0.6 mm preload as the
camera/battery contact face, preventing the doors from rattling when the case
is closed.

With `BUILD_REFERENCE_MOCKUPS = True`, the script also creates the exact
generated dual-fan holder and attached three-prong adapter, two installed
80 x 80 x 27 mm padded fan solids, four procedural 33.5 x 12.5 x 40.56 mm
battery solids, and two procedural 50 x 10 x 18 mm door solids for visual
inspection. They are reference-only scene objects, not additional STL
dependencies or print outputs.

## Alternate two-fan-case loadout

The fan-case loadout is an alternative to the complete dual-fan storage stack,
not an additional tier. Remove the lower dual-fan cradle, upper equipment tray,
normal lid pad, and dual-fan assembly before installing these two parts:

- `mission1_field_case_fan_case_pair_lower_insert_tpu.stl`
- `mission1_field_case_fan_case_pair_lid_pad_tpu.stl`

The 224 x 148 mm lower insert reuses the full preserved case interior for two
fully assembled fan-case objects. Each stored object includes its installed
MISSION 1 camera, current fan-case shell/insert/buttons/baffle/front retainer, a
direct-mounted 40 x 40 x 20 mm rear fan, and the current
`wrapping-fan-cover`. It also includes the three installed M3 x 40 case bolts
and their 10 mm-diameter, nominally 2.5 mm-thick low-profile thumb-nuts.
Generation temporarily disables the fan-case generator's
optional 60 mm rear adapter because the 40 mm fan uses the shell's direct
32 x 32 mm mounting pattern. The exact current complete envelope is
97.77 x 93.40 x 68.57 mm per assembly. Both fit side-by-side with the existing
internal width, depth, and height unchanged.

The bolt length is resolved from the fan-case geometry rather than represented
by a generic front allowance. The current captured hex-head bearing seat is at
Y = 11.5924 mm, the rigid swing-gate front face is at Y = 46.8 mm, and the
M3 x 40 tip is at Y = 51.5924 mm. Each shaft therefore projects exactly
4.7924 mm past the gate and approximately 2.2924 mm past a seated 2.5 mm
thumb-nut. The three 10 mm nut envelopes remain inside the camera's existing
front extent and the fan-case shell's width/height extent, so they do not
increase the complete storage envelope. Adjust `FAN_CASE_THUMB_NUT_THICKNESS`
if the measured low-profile nuts differ.

The stored fan cases remain upright: the source row of two fasteners is at the
physical bottom and the single fastener is at the top. Only each wrapping cover
turns half a rotation around its fan/global Y axis, placing the current TOP wire
notch upward without inverting the camera or case. The 12 mm base deck retains
the 3 mm assembly floors. Above it, four 3.2 mm-thick corner-guide segments per
assembly rise to 28 mm, engage 24.5 mm of the complete assembly height, and
leave approximately 44 mm exposed for a full-hand lift. The original 1 mm plan
clearance remains, while a 0.8 mm tapered lead-in and wide front, rear, and side
release gaps prevent long hard-TPU walls from dragging. Local 1.4 mm-floor
reliefs still leave more than 0.5 mm of air beneath the two low 10 mm thumb-nuts
so the thin hardware does not carry the case weight.

Two 64 x 36 mm rounded wells each carry one coiled fan lead. The modeled cable
centerline is 56 x 28 mm with a 6 mm corner radius, for 157.7 mm of path around
the loop versus the required 152.4 mm (6 inches). Each 8 mm route is derived
from the wrapping cover's current `CABLE_NOTCH_SIDE` and `CABLE_NOTCH_OFFSET`
and cuts through the full-height front guide; the exact scene reference follows
the transformed notch through that throat to its well. Raised flexible docks
retain the two PWM plugs; the default user-tunable plug envelope is
16 x 10 x 8 mm, its free channel is 11 mm wide (0.5 mm clearance per side),
and only the 0.6 mm-per-side retention nubs enter that channel. Measure an
unusually large molded plug and adjust `PWM_CONNECTOR_ENVELOPE` before printing
if necessary.

The unused center of each cable loop contains one rotated 34.5 x 13.5 x 21.8 mm
battery pocket, for exactly two batteries in this alternate loadout. The cable
still has at least 3.25 mm clearance from each 38.5 x 17.5 mm battery tower.
Approximately 18.8 mm of each battery remains exposed for removal; small
opposed nubs create only 0.15 mm nominal local interference instead of making
the full pocket a friction fit. Two 50.8 x 11 x 11 mm battery-door pockets use
the center lane between the wells. They store exactly two 50 x 10 x 18 mm doors,
leave 7 mm proud, and use the same 0.15 mm local retention. The front scallop,
guide openings, and cable wells give direct hand access to the assemblies and
insert.

The lower insert's maximum printed height is now 28 mm at its segmented guides;
its outer dimensions remain 224 x 148 mm. The keyed 224 x 148 x 31.57 mm lid
pad replaces the normal camera pad. Four lightweight columns contact the broad
rear-shell edges with 0.6 mm preload while clearing the cameras and controls.
Do not stack either alternate part with any dual-fan-loadout insert.

The exact references are built directly from the current local fan-case,
MISSION 1 dummy, and wrapping-cover generators. The production Make target
checks two cameras, two direct 40 x 40 x 20 mm fans, two wrapping covers, six
M3 x 40 bolts, six 10 mm thumb-nuts, two batteries, two battery doors, both
cable coils, and both PWM plugs for fit, guide engagement, retention, and
collision before exporting. A
source change that no longer fits the preserved shell therefore fails
generation instead of silently producing an incompatible storage insert.

## Lid logo

The lid text is `GoPro Missions`, set in the compact embedded Neuropol
GoPro-style face. Its minimum stroke is widened from 1.475 mm to 2.2125 mm,
exactly 50% thicker than the original. Two broad, rounded hockey sticks cross
above the text with opposing blades and a compact rounded puck centered below
them, while four small blocks below the text follow the familiar GoPro layout.
The artwork, lettering, and blocks use the same orange material and are joined
into one shallow 0.8 mm flush-inlay STL.

With the default `PRINT_TPU_GASKET_WITH_LID = True`,
`mission1_field_case_ams_project.3mf` contains the lid as one aligned
three-material compound object:

- black shell
- orange hockey artwork, `GoPro Missions` text, and four orange blocks
- hollow hard-TPU lid gasket

The 3MF declares black and orange rigid filaments plus hard TPU as filament 3.
Use an AMS-compatible hard TPU, a TPU-capable multimaterial system, or the
printer's supported external-spool/manual-change workflow. Do not feed ordinary
soft TPU through an AMS that does not support it.

For another slicer, import these files together without changing their relative
positions:

- `mission1_field_case_lid.stl`
- `mission1_field_case_lid_logo_orange_inlay.stl`
- `mission1_field_case_gasket_tpu.stl`

The shell and orange STL both begin at Z = 0. The integrated gasket remains at
its assembled Z = 9.8-11.25 mm so all three files share the lid coordinate
system. Import them as one multipart object. The black lid surrounds matching
0.8 mm-deep logo pockets while the orange body fills them, so black and orange
jointly form one continuous build-facing first layer. The generator verifies
that every orange island touches the build plate, bonds to the pocket ceiling,
does not overlap the shell, and combines with the black shell to cover the
lid's complete first-layer footprint. This avoids placing the entire black lid
0.8 mm above isolated orange letters, which would otherwise make a slicer
bridge that layer or generate broad support beneath it.

## Hollow TPU lid gasket

The default integrated gasket is a closed hollow tube rather than a solid hard-
TPU ring. Its 2.2 x 1.45 mm section contains a continuous 1.1 x 0.45 mm air
channel, with 0.55 mm side walls, a 0.60 mm floor, and a 0.40 mm roof. The
internal void removes 366.341 mm3 of TPU and lets a relatively hard material
compress more readily while preserving the existing 0.25 mm proud seal height.
The short 1.1 mm internal bridge needs no generated support.

The generated 3MF enables the slicer's native `Use beam interlocking` option
for the compound lid. It uses 0.8 mm beams, two beam layers, two cells of
interlocking depth, a 22.5-degree orientation, and zero boundary avoidance so
the narrow gasket-to-lid interface is not skipped. The 0.60 mm gasket floor
leaves three nominal 0.20 mm TPU layers at that interface. Geometry validation
proves a continuous matching shell/TPU interface and zero overlapping volume
before the slicer generates its alternating-material beams.

Set `PRINT_TPU_GASKET_WITH_LID = False` before generation to restore a separate
Z = 0 hollow-gasket STL and its own TPU plate. That mode removes the gasket from
the compound lid and disables project beam interlocking; seat the separately
printed gasket in the unchanged lid channel during assembly.

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
The M3 x 30 screw fully engages the 2.4 mm nut thickness, reaches 2.82 mm past
the nut-pocket floor, and projects approximately 0.12 mm beyond the inboard
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
exposed upper half remains the retention bead. The lid-side impact walls
carry both ends, keep the 20.48 mm-wide hook from walking sideways off the
catch, and stand proud of it to deflect impacts. Each one is now the literal
vertical continuation of its base protector: the same 6 mm axial footprint and
the same 21 mm projection from the case wall to the common front edge. Its side
profile is one 21 mm-long by 16 mm-high rectangle with straight 90-degree edges,
not a narrow column, wedge, or triangular tower. The wall begins directly on
the lid's original Z = 0 outer-top print plane; only the exposed top/front
corner receives a 2 mm radius. A hidden 0.5 mm rectangular
root tab bonds the wall into the existing 4 mm lid plate without extending into
the base's closed envelope. The lid shell, flange, and closure dimensions are
unchanged outside these four protector walls, and the lid still prints flat on
its outer top.

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
screw head and nut while the inner pivot ears preserve 0.2 mm lever clearance
on both sides. Together with the lid towers, the cheeks
protect the closed hardware from side hits and snags while leaving the full
center finger corridor open. A deliberate 0.1 mm offset prevents coincident
ear/guard faces while preserving 0.3 mm between each guard and the moving
lever. The horizontal catch rail is the only short
bridge that may benefit from tuned bridging or localized support. The load
ledge turns that bridge into an 8.6 mm-deep structural shelf tied into the lid
wall and towers; the guard ramps themselves do not require support in the
exported orientation, and the captive nut pockets close with 45-degree roofs.

The uncompressed lid begins 0.25 mm above its hard seated position. Pressing
the broad lever inward places its flat pad against the load ledge, draws the
lid down onto the gasket, and passes the linkage over center. The generated
geometry verifies zero hard-seated hook/lid intersection, 1.553362 mm3 minimum
total capture and 0.228876 mm3 of flat-pad capture during an attempted 0.15 mm
lid lift, 8.102795 mm3 total preload and 2.590539 mm3 of isolated flat-pad
preload at the full 0.25 mm uncompressed gasket position, and 28.248630 mm3
minimum engagement during a 0.60 mm outward-peel attempt. It also verifies
3.515401 mm3 minimum capture at 12 degrees open and complete rail/ledge release
at 24 degrees. The complete coupled opening path has zero hook/base, hook/lid,
and lever/hook collision.

The source toggle architecture is retained, with its moving pivot adjusted
for the deeper over-center travel. Opposed hidden spherical snap detents in
both base ears center the lever and prevent normal
pivot play from bypassing the snap. The ear spacing leaves 0.2 mm axial
clearance per side, while the larger opposed dimples clear both worst-case
axial positions at the fully seated pose. A dedicated quarter-degree exact
sweep at -0.2, 0, and +0.2 mm verifies zero closed contact, at least 0.0560 mm3
of peak release engagement everywhere in that range, and complete release by
22 degrees open. Pushing the lever in the wrong direction is stopped by the
base across the same axial range.

`LATCH_HOOK_OVERALL_LENGTH` directly configures the finished moving hook's
true overall length about its unchanged link-pivot boss after removing the
source's narrow central crown fin. The original finned source is 50.241260 mm;
the usable crownless reference body is 46.703189 mm. The configured 45.203189 mm
default is exactly 1.5 mm shorter than that body, while the separately generated
load-bearing pad remains fixed relative to the lid. In the installed closed
pose the broad remaining hook cheeks stay 1.869 mm below the protector walls,
with no thin central "mohawk" above them.
The moving pivot is also positioned for 0.10 mm of true over-center travel:
hook draw peaks at dead center, then relaxes by that small amount when the lever
seats fully. The toggle therefore resists reopening mechanically; the spherical
detents add a second release bump instead of being the only feature holding the
lever shut.

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
nut on the case-center face. Both integrated mounting lugs retain their
existing 3.9 mm bores, which already provide free travel for an M3 screw.

Each 5.5 mm-maximum-diameter by 3.0 mm-tall socket head is fully recessed in a
6.0 mm-diameter by 3.2 mm-deep cylindrical counterbore with a printable
45-degree roof; use a 2.5 mm Allen wrench. The matching standard nut is fully
recessed in a 5.8 mm-across-flats by 2.7 mm-deep support-free hex pocket. The
locally thickened fork ends retain a complete 1.0 mm floor between each recess
and the fixed-lug sweep cavity. An M3 x 12 screw fully engages the 2.4 mm nut,
reaches 4.2 mm past the nut-pocket floor, and projects 1.5 mm beyond the
inboard handle face.

The handle pivot is centered horizontally and vertically on the assembled case
front: X = 0 and Z = 86.9 mm. The 95 mm-wide folded bar occupies only the
reserved center zone. The two exact latches retain their compatible X = ±82 mm
centerlines; their
moving levers remain 22.16 mm from the handle's full folded and swinging X
envelope. The 6 mm integrated guards retain 15.86 mm from that envelope, and
the installed latch M3 screw tips retain 15.74 mm. The two old
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
and verifies at least 0.687214 mm3 of blocking intersection at every sampled
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
is attached. Their smaller diameter clears the base rear wall;
generated solid probes and deliberate axial-overtravel probes verify both
stops and retention.

### Optional 68D TPU snap-on lid

`mission1_field_case_lid_tpu_68d_snap.stl` is a complete alternative lid for
TPU-for-AMS with a Shore rating of 68D. It replaces
`mission1_field_case_lid.stl`; never stack the two lids. The default rigid lid
and its deliberate 70-degree slide-off receiver remain unchanged. The TPU lid
keeps the same case closure, latch protectors, gasket channel, and 4.8 mm seated
rod receiver, but narrows the snap throat to 3.9 mm and flares it to a smooth
5.5 mm mouth. Each of the two original 22.8 mm lid receivers is divided into
three short clips with 1.2 mm axial relief gaps, allowing six local flex zones
instead of bending one long barrel.

With the 4.1 mm rod already centered in the three base knuckles, hold the TPU
lid partly open, align both banks of mouths with the rod, and press the clips
onto it progressively. The hard TPU can flex past the 3.9 mm throat and recover
around the 4.8 mm seat. To remove it, support one short clip bank at a time and
peel it back off the rod; avoid sharply folding the lid plate or pulling one
end of the full hinge at once.

Print `mission1_field_case_tpu_68d_hinge_coupon.stl` before committing to the
full TPU lid. It contains four breakaway, dot-coded clips with 3.8, 3.9, 4.0,
and 4.1 mm throats: one dot is 3.8 mm, two dots is the nominal 3.9 mm, three
dots is 4.0 mm, and four dots is 4.1 mm. Test the actual 4.1 mm rod using the
same filament, layer height, wall count, orientation, and dry-filament state as
the lid. Each coupon receiver uses the actual 6.8 mm clip width and reproduces
the lid's plate-to-flared-rim-to-barrel root cross-section in the same exported
print orientation. Use the same removable support-interface settings inside
all four coupon receivers that will be used inside the TPU lid clips; a changed
interface gap can distort the throat comparison. Choose the smallest throat
that snaps repeatedly without whitening, cracking, or requiring excessive
force, then set `TPU_HINGE_SNAP_THROAT_WIDTH` to that value if it differs from
3.9 mm.

The optional TPU lid is not included on the default rigid-lid 3MF plate. Import
its STL with `mission1_field_case_lid_logo_orange_inlay.stl` as aligned parts if
a contrasting flush logo is wanted. The gasket uses the same unchanged
channel. In the default integrated-gasket coordinate mode, also import the
gasket STL as an aligned part; with `PRINT_TPU_GASKET_WITH_LID = False`, install
the separately printed Z = 0 gasket after the lid is complete.

## Suggested printing

- Base, lid, broad latch levers, handle bar, and hinge pin: PETG, ASA, nylon,
  or another impact-tolerant rigid filament; 0.20 mm layers, four walls, and at
  least 25% infill.
- The upper moving latch hooks may be printed in hard TPU. Use the stiffest TPU
  your printer handles reliably, at least five walls, and high infill around
  the flat bearing pad, round retention boss, and link-pivot end. Soft 95A
  tray-style settings are not recommended for this load-bearing part.
- Lower fan cradle, upper equipment tray, and lid pad: TPU 95A, two or three
  walls, and 15-20% infill.
- Alternate fan-case lower insert and lid pad: TPU 95A or a comparably resilient
  protective material, three walls, and 15-20% infill. Keep the PWM dock nubs
  flexible; do not fill the plug channels with support.
- Optional snap-on lid and hinge coupon: TPU-for-AMS 68D, 0.20 mm layers, at
  least four walls around the hinge clips, and enough top/bottom layers to make
  the lid plate continuous. Print the coupon first with identical settings.
- Gasket: relatively hard TPU with a 0.4 mm nozzle and 0.20 mm layers. The air
  channel is modeled into the STL, so do not enable support or gap filling in
  that closed void. The gasket is for dust and splash resistance, not certified
  waterproofing.
- Print the base, compound lid, both trays, lid pad, latches, and handle bar in
  their exported orientations. Their broad faces are already on the bed. With
  the default option, the gasket is already positioned inside the compound
  lid; the standalone gasket STL is an aligned multipart component, not a
  separate Z = 0 print.
- The case-side latch and handle mounts rise on 45-degree lower webs and do not
  require support. Do not place support inside their teardrop pivot bores.
- The rigid lid has two 22.8 mm hinge slots in its broad-face-down orientation;
  add removable support in both. The optional TPU lid instead has six 6.8 mm
  clip slots, and the coupon has four matching 6.8 mm receivers. Use the same
  removable support-interface settings for the TPU lid and coupon so support
  removal does not bias throat calibration. Remove support completely and
  verify the actual 4.1 mm bar moves through every selected receiver before
  assembly.
- Print the optional headless 4.1 mm hinge pin on its D-shaped flat, or cut a
  4.1 mm metal bar to 151 mm. Verify the actual bar against a small bore test
  before printing the full base.

Test camera, battery, latch, handle, and hinge fits before field use. Pocket,
pivot, and press-fit dimensions are constants near the top of the Python file
and can be regenerated without editing an STL.

## Case assembly

1. Press the lower fan cradle into the base. Turn the complete dual-fan
   assembly rear-grille-down, point its attached adapter toward the front/latch
   side, and seat both fan-frame contact regions in the shallow locator pocket.
   Lower the upper equipment tray over the support arm until the arm passes
   through the rounded opening and the tray rests on both rigid side rails.
   Load the two removable battery doors in its shallow outer pockets if
   carried; each door remains 7 mm proud.
2. With the default integrated print, inspect the beam-interlocked TPU gasket
   for a continuous bond to the lid channel. If the separate-gasket option was
   used, seat the hollow TPU ring in the channel. Fit the TPU pad with its
   asymmetric notch over the matching rigid boss.
3. Feed and center the 151 mm-long, 4.1 mm bar (or headless printed D-profile
   pin) through the three base knuckles, leaving both ends about 0.5 mm inset.
   Hold the lid approximately 70 degrees open. Align both rearward-opening
   receivers with the installed bar and slide the lid diagonally down and rear
   along the slot direction, then rotate it closed. The base
   blocks that same removal path through 65 degrees, while the two solid lid
   stops retain the bar axially.
4. Install each latch with one M3 x 30 ISO 4762 / DIN 912 Allen socket-head cap
   screw, one standard M3 nut, and a moving-link rod cut to
   `LATCH_LINK_ROD_LENGTH`. Install the separate handle bar with two M3 x 12
   Allen socket-head screws and two standard M3 nuts, one set per side.
5. Load the two opposed cameras with their soft lens hoods in the flared ends,
   then load four batteries terminal-down. Remove the cameras and batteries,
   place two fingers in the front scallops, and lift the upper tray straight up
   along the fan arm whenever the fan assembly must be removed.

For the alternate fan-case configuration, omit steps 1 and 5. Seat its lower
insert directly on the case floor, coil each fan lead in its dedicated well,
route the visible lead from the upward wrapping-cover notch through the 8 mm
throat, and slip the PWM plug into the matching outer dock. Press one battery
into the tower inside each cable loop and place both battery doors in the two
center slots. Lower each complete fan-case assembly upright between its four
corner guides with its two-bolt row down and single bolt up. Fit the alternate
keyed lid pad in place of the normal lid pad. The installed cameras, 40 mm fans,
and wrapping covers remain on the fan cases during storage; the dual-fan
assembly and all three of its TPU storage tiers stay out of the case.

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
