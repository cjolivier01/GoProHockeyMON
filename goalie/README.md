# Printable Hockey Goalie Mannequin

`hockey_goalie_mannequin_blender.py` generates a full-scale goalie mannequin in
a ready stance. The default build contains a rigid PETG/ABS/ASA skeleton, laced
TPU dressing forms for real goalie gear, simplified TPU display gear, and a
node-braced floor stand. Every exported part is centered in its documented
print orientation and checked against a conservative 245 x 245 x 195 mm usable
volume inside the requested 250 x 250 x 200 mm printer envelope.
The export path explicitly triangulates each isolated print-pose copy, then
parses every delivered binary STL to reject duplicate or zero-area facets,
non-manifold edges, disconnected shells, nonzero bed offsets, and oversize
geometry.

## Generate the model

Blender 4.4 or newer is recommended:

```sh
/home/colivier/Apps/Blender/blender --background --factory-startup \
  --python-exit-code 1 \
  --python hockey_goalie_mannequin_blender.py -- \
  --output-dir goalie_output
```

The managed output directory contains an assembled `.blend`, one STL per part,
`goalie_parts_manifest.csv`, an explicit mate/fastener table in
`goalie_connections.csv`, a configuration-derived hardware BOM, and a fit and
prototype guide. The generator refuses a nonempty output directory unless it
already bears its management marker. Rebuilding replaces generated files
inside a marked directory, so do not store unrelated files there.

## Size and output options

`--stature-mm 1880` controls limb lengths and the default proportional fit
values. Supported stature is 1500-2050 mm. Real gear varies enough that the
following independent millimeter options should be measured and supplied:

- `--shoulder-width-mm`, `--chest-width-mm`, `--chest-depth-mm`
- `--waist-width-mm`, `--waist-depth-mm`
- `--head-width-mm`, `--head-depth-mm`
- `--thigh-circumference-mm`, `--calf-circumference-mm`
- `--upper-arm-circumference-mm`, `--forearm-circumference-mm`
- `--hand-width-mm`, `--foot-width-mm`, `--gear-clearance-mm`

The generated fit guide records the exact values and calls for representative
coupon prints before committing to the full set. `--gear-clearance-mm` is a
per-side allowance added to the soft TPU form—not empty air clearance; the fit
guide explains how to work backward from measured gear internals.
The TPU hand form must also clear its 68 x 54 mm rigid palm bracket, so its
actual outer envelope cannot be smaller than 78 x 64 mm. The generated fit
guide reports the derived hand-form width and depth; use those derived values,
not only `--hand-width-mm` plus clearance, when checking a real glove or
catcher. At small settings this structural floor overrides the usual
subtract-twice clearance calculation.
If a configured chest is nearly as wide as the shoulders, the rigid shoulder
pivots automatically move outward enough to clear the chest form; the fit guide
records that derived structural span. The front/back upper torso forms retain
their height, while shorter side forms provide deliberate armpit relief.

Other switches:

- `--no-gear` omits the costume/display pads, chest pieces, catcher, and blocker.
- `--no-body-shell` emits a direct-to-structure mannequin and also implies
  `--no-gear`, avoiding gear references to omitted TPU forms.
- `--no-stand`, `--no-export`, and `--no-save-blend` disable those outputs.

## Materials and joints

Print `01_STRUCTURE` and `04_STAND` parts in PETG, ABS, or ASA. Use at least six
perimeters and 30-40% gyroid infill; use the higher settings in the manifest for
stand nodes/brackets. Do not use brittle PLA for load-bearing parts. Print body
forms and display gear in 95A TPU with four or five perimeters.

Each rigid link has an M8 center pivot and an offset M5 straight-lock bore.
Install both bolts at every print split so long members cannot fold as clamp
friction relaxes. Leave the M5 bore empty only at an intentional knee, ankle,
elbow, or wrist pivot. Shared plane normals and assembly-level assertions verify
that every registered mating bore is coaxial and has complementary MALE/FEMALE
terminals.

Pelvis and shoulder plates use non-interpenetrating butt/stacked laps with
globally paired holes. Angled hip, shoulder, and diagonal-stand brackets seat
on separate full-area rigid wedges; the wedges print bracket-face-down, while
the broad pelvis, shoulder, and rail panels remain genuinely flat on the bed.
Wedge depth, through-bore depth, and each corner's M5 bolt length are derived
from the posed geometry and written to the connection table and hardware BOM.
Shallow one-, two-, three-, and four-dimple groups on the terminal-facing side
of every wedge bracket physically map those corner-specific bolt lengths to
the printed holes; lay out the bolts before the washers cover the marks.
The stand node uses face-accessible heat-set inserts, while the rear pelvis
saddle uses M6 through-bolts with accessible front-face nuts over paired
drilled 50 x 40 x 3 mm steel backing plates installed 50 mm horizontally;
the saddle and its pelvis holes are omitted
entirely with `--no-stand`.
TPU boot and hand forms are hollow, cavity-up clamshell prints with modeled
lacing holes; each hand form is asymmetric and wrist-open, with a clipped
planar distal web that does not occupy the palm-bracket or forearm volume. The
hand/head forms include reinforced rigid-mount patterns. Limb, torso, and
display-gear pieces have modeled attachment holes.

Each green TPU thigh, calf, upper-arm, and forearm form is also a two-piece
clamshell rather than a loose friction-fit tube. A configuration-length M5
threaded rod passes through aligned bores in the front TPU mounting web, rigid
link, and rear TPU mounting web; two 20 mm fender washers and nyloc nuts clamp
the complete form directly to the skeleton. Three paired holes along both long
seams are then laced with shock cord or reusable ties. The through-rod is the
mandatory retainer and allows the forms to be mounted after skeleton assembly.
Before tightening, leave the caps off and center each rod so the bare-tip
projection measured from the adjacent outer sleeve face differs by no more than
1 mm between front and rear. Hold it centered while tightening, deburr it, and
fit low-profile caps that extend no more than 3 mm past each rod end.
Optional printed knee/shin pad
modules sit on the world-+Y front of the leg and strap around these mounted
forms, never on the calf-side rear. Use low-profile rod caps no larger than
20 mm outside diameter. Each panel's two integral rear saddle rails seat broadly
on the TPU sleeve outside that washer/cap envelope; their position and width
also preserve at least 2 mm beside the closest 5.2 mm sleeve seam bore and its
installed 4 mm cord. The open center channel keeps strap tension from turning
the cap into a point-load standoff. Confirm the seam-cord exits remain outside
the rails and tighten only until both rails seat.
The configuration-derived strap cut lengths are listed per connection;
`HARDWARE_BOM.txt` totals those 20 cuts plus the glove/wrist allowance and 10%
waste.

## Stand and assembly sequence

Use `goalie_connections.csv` as the authoritative mate table and hardware list:

1. Bolt each rigid print split with its M8 pivot and M5 straight-lock bolt.
2. Sandwich the pelvis butt seam between its top/bottom lap plates, join the
   stacked shoulder laps, then install the matching wedges and brackets with
   the single through-bolt stacks listed in the connection table.
3. Place the TPU limb clamshell halves around the completed rigid links, install
   each listed M5 through-rod with fender washers and nyloc nuts, center its
   front/rear bare-tip projections within 1 mm while tightening, deburr it, fit
   the specified low-profile caps, and then lace both longitudinal seams. No
   pivot disassembly is required.
4. Assemble the lower and upper upright around the rounded stand node; its four
   clipped planar insert bosses keep the diagonal and upright brackets separate.
5. Install both top-corner lock plates, both foot plates, and all four base laps.
6. Through-bolt the stand and foot plates to one 900 x 900 x 18 mm plywood sheet.
7. Pass the purchased M10 forged eye bolt through the printed fairlead and the
   full stand node, then connect a tether rated at least 1 kN to a structural
   wall or floor anchor.
8. Dress the mannequin, repeat the documented 150 N minimum tip/load test, and
   re-test after 24 hours under dressed static load.

## Safety and prototype status

This is a display and equipment-fit mannequin, not a person-supporting device.
Printed pad, chest, blocker, catcher, head, and boot pieces are costume/display
forms only. They are not certified protective equipment and must never be worn
for hockey, practice, impact testing, or any safety application.

The generator verifies print orientation, usable build volume, manifold shells,
joint centers/axes/terminal sexes, paired mount patterns, and selected assembly
contacts. Printed strength, creep, real-equipment fit, site anchoring, and stand
stability still require the coupon and dressed-load physical tests in the fit
guide with your printer, filament, hardware, and gear.
