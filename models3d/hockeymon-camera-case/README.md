# HockeyMON camera case

Build from the repository root:

```sh
make -C models3d hockeymon-camera-case
make -C models3d dim-pdf
make -C models3d check-dim-pdf-sync
make -C models3d check-hockeymon-battery-slot
make -C models3d check-hockeymon-fan-cover
make -C models3d check-print-3mf
```

## Printable 3MF

`make -C models3d hockeymon-camera-case` now also generates
`models3d/hockeymon-camera-case/hockeymom_cam_case.3mf` alongside the STLs.
It contains all **12 default printable parts**, each labeled on its own
**250 × 255 mm plate** in the same orientation as its STL, resting on Z=0.
Purchased hardware, battery mockups and assembly references are excluded.
Optional printable parts follow the active configuration; stale STLs are
never collected from the output directory.

Open the project in Bambu Studio or OrcaSlicer to retain separate plates.
Choose your printer and material profile before slicing; the project does
not assign either. Its generic 0.4 mm nozzle and 250 mm height entries are
import placeholders; replace them with your actual machine profile. Readers that only support standard 3MF meshes may require
arranging the parts onto separate plates. Use supports under the fan fairing's
tail. The near-bed-width base and lid need no outward brim or skirt.
For custom Blender runs, set `EXPORT_3MF = False` for STL-only output.
The Make target always generates both formats.

## Streamlined fan cover and rear corners

![Swept fan cover from the rear](docs/images/streamlined_fan_rear.png)

![Fan cover side profile](docs/images/streamlined_fan_side.png)

![Top view and rounded rear case corners](docs/images/streamlined_fan_top.png)

The fan fairing now sweeps **52 mm aft** into a low, rounded tip above the
battery bay. Its broad shoulders blend into the existing fan grille, which
still slides forward after removing its top locking screw. The fan mounting
positions and two hidden fairing screws stay in place. The hollow tail uses
a surface-normal wall offset so its shallow roof retains the selected wall
thickness. Print the fairing open side down with removable supports beneath
the tail; the separate grille still prints flat without supports.

Rear case corners use a **24 mm radius**, with the outer envelope margin
controlled separately so rounding does not grow the case beyond the printer
limit. The 40 mm USB space, rear screw access and battery fit are checked
against the rounded shell. Use the matching base and lid for this revision.

## Internal rear battery bay

![Battery centered across the bottom mount with one-sided USB space](docs/images/centered_battery_plan.png)

![Battery inside the enlarged base, with the lid removed](docs/images/rear_battery_loaded.png)

![Enlarged case with the battery enclosed by the main lid](docs/images/rear_battery_closed.png)

![Empty internal slot and camera chamber](docs/images/rear_battery_empty.png)

The **26.3 × 70 × 138 mm** battery goes **inside the case**, upright:
26.3 mm along X (front to back), 138 mm along Y (across the back), and
70 mm vertically. The pack spans **Y = −69 to +69 mm**, centered east–west
on the bottom bolt mount at **Y = 0**. Its rearward X position and seat height
stay unchanged. Its USB-A/USB-C face points toward **+Y**, into a
**40 mm internal clearance zone** for plugs and cable bends. The plug region extends over the face above the low corner stops, with an
open path through the center below them. The USB zone spans **Y = +69 to
+109 mm**. The opposite side has matching empty space so the outer base
and lid envelope remains symmetric about **Y = 0**. The generator checks
that the entire outer outline matches its reflection within 0.001 mm.

The base and matching main lid extend rearward, with a taller roof to keep
the footprint within a **250 × 255 mm print bed**. The default base measures
**249.25 × 237.99 × 90 mm**. Main body height is 94.653 mm; the external fan
and grille sit above it. Camera positions and the worm-shaft exit remain
unchanged. Rear lid screws move behind the battery and stay accessible.
Use the matching base and lid from this revision. The largest part has only
0.75 mm total spare width on a 250 mm bed, so slice it without an outward
brim or skirt. Each part exports separately in its intended print orientation;
the generator checks each part against 250 mm in X and 255 mm in Y,
rotating it 90 degrees in the print plane when needed. Each part is printed
individually; they do not need to share one plate.

![Low battery stop tabs at the USB end](docs/images/battery_bottom_stops.png)

Matching pairs of thick tabs at **both ends** limit battery movement in
both directions along its length. This removes the heavier full-height
wall from one end and makes the cradle and its retaining bar symmetric. Each projects **3 mm**
across a bottom corner, rises **4 mm above the seat**, and is **4 mm thick**
along the end. The lowest 4 mm at those two corners must be free of ports.
The center of the USB face and the space above the tabs remain open, with
40 mm for plugs and cable bends. The top retaining bar still holds the pack
down; remove it before lifting the battery past the stops.

The two-wall cradle has **0.6 mm clearance per side**, giving a **27.5 mm
clear width** and **139.2 mm length** between its end stops. Its 3.2 mm walls
rise to Z=60 mm. The pack rests on the solid seat at Z=5.7 mm, with its top
at Z=75.7 mm, below the lid and clear of the fan opening.

A single **47.5 × 16 × 4 mm screw-on bar** holds the battery down. Print
`hockeymom_cam_case_battery_bracket.stl` flat and use **two M3 × 10 mm
socket-head screws**. For the default rigid base, install **two M3 × 5 mm
heat-set inserts** in the cradle posts (4.0 mm pockets with 4.8 mm lead-ins).
The posts have blind tip clearance below the inserts. TPU-base mode uses
pointed M3 screws and pilot holes under the existing material policy.

Remove the main lid and attached fan assembly, lower the battery into the
cradle, and place the bar across its middle. Snug both screws: the post tops
sit 0.25 mm below the battery top so the bar can clamp the pack. Avoid
forcing the bar down or overtightening against the battery housing. To remove
the battery, remove the lid, unplug the leads, undo the two screws, lift off
the bar, and lift out the pack. The bar and screw heads stay inside the case.

The battery, cradle, bar and USB plug envelope sit at least **8 mm aft of
the protected top-fan/camera flow region**. The fan opening's full vertical
projection remains clear for intake or exhaust. A validated 6 mm cable exit
corridor connects the USB space to the camera chamber. Route leads along
the inside of the case with slack for camera adjustment; keep loose loops
away from fan and camera openings. The corridor validates the bay exit;
the exact purchased leads and their route to each camera need fitting during
assembly. Geometry checks establish clearance, not measured cooling performance.

Print the base upright on its bottom and the bar flat. The battery and screws
in the previews are reference objects. Check physical pack fit and retention
before field use.

`REAR_BATTERY_*` settings control pack dimensions, fit, USB space, cooling
separation and bracket hardware. The generator solves the rear footprint and
screw targets, protects the camera/mechanism perimeter, and checks rear height
taper. `PRINT_BED_WIDTH_MM` / `PRINT_BED_DEPTH_MM` default to 250 / 255.
Set `REAR_BATTERY_SLOT_ENABLED =
False` to restore the original plan footprint or use rear-wall fans; height
settings remain independently configurable.

The shell envelope, battery, cradle, retaining bar and fan are centered
east–west. The camera adjustment mechanism and camera internals retain
their functional layout; exact assembled balance also depends on the actual
component masses, print infill and cable routing. As a uniform-solid plastic
comparison, the base centroid moved from Y=+4.58 to +1.84 mm and the lid
from +4.98 to −0.16 mm; the battery holder balances within 0.001 mm of Y=0.

Validation checks outline symmetry, cradle balance, closed-case containment, battery and bracket removal,
screwdriver access, screw-hole alignment and depth, USB/cable clearance,
post/mount keepouts and manifold geometry. Regressions exercise one 120 mm fan,
a 60 mm fan pair, rigid/TPU receivers and oversized-export rejection. The
dimension PDF includes the upright bay and all configuration values.
