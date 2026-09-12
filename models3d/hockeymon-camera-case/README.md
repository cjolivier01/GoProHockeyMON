# HockeyMON camera case

Build from the repository root:

```sh
make -C models3d hockeymon-camera-case
make -C models3d dim-pdf
make -C models3d check-dim-pdf-sync
make -C models3d check-hockeymon-battery-slot
```

## Internal rear battery bay

![Battery inside the enlarged base, with the lid removed](docs/images/rear_battery_loaded.png)

![Enlarged case with the battery enclosed by the main lid](docs/images/rear_battery_closed.png)

![Empty internal slot and camera chamber](docs/images/rear_battery_empty.png)

The **26.3 × 70 × 138 mm** battery goes **inside the case**. Lay it flat:
70 mm along X (front to back), 138 mm along Y (across the back), and
26.3 mm vertically. Its USB-A/USB-C face points toward **+Y**, into a
**40 mm internal clearance zone** for plugs and cable bends. The combined
pack and USB space is centered across the rear bay. Connector positions
are not modeled; the entire 70 × 26.3 mm face is reserved.

The base and main lid extend rearward together. The default base is about
**294 × 231 × 68 mm**; the main lid closes at the existing 72.653 mm body
height. Camera positions and the worm-shaft exit stay unchanged. Rear lid
screws move behind the battery so they support the enlarged lid and remain
accessible. This revision needs the matching enlarged base and lid; check
the solved footprint against your printer's build area before slicing.

The internal slot has 0.6 mm clearance per side: **71.2 mm clear width** and
**139.2 mm length** to its open USB end. The battery rests at Z=5.7 mm and
its top is Z=32 mm, below the closed lid. The cradle walls are 20 mm high
and 3.2 mm thick. The ordinary case floor supports the cradle.

Remove the main lid and its attached fan assembly to load the battery.
Use **two 15 mm hook-and-loop straps**, approximately 250 mm long and no
more than 2 mm thick. Thread them through the 16 × 2.5 mm floor tunnels,
up the outside of the cradle walls and over the pack; tighten both straps.
Both straps and the USB plugs remain inside the closed case. To remove the
battery, remove the lid, unplug it, release both straps and lift it out.

The battery, cradle, straps and USB plug envelope sit at least **8 mm aft
of the protected top-fan/camera flow region**. The fan opening's full vertical
projection stays clear for intake or exhaust. A validated 6 mm cable exit
corridor leads from the USB space into the camera chamber. Route the camera
leads low along the inside of the case, with slack for camera adjustment;
keep loose loops away from the fan and camera openings. The corridor checks
access from the battery bay; the exact purchased leads and their final route
to each camera still need to be fitted during assembly.

Print the base upright on its bottom. The strap tunnel roofs are short
bridges. Straps and the battery are purchased parts, shown as references in
the preview. Check physical fit and strap security before field use.

`REAR_BATTERY_*` settings control battery dimensions, fit, plug space,
cooling separation and straps. The generator derives the enlarged rear
footprint and rear screw targets, protects the original camera/mechanism
perimeter, and checks the resolved height taper. It rejects a configuration
that cannot retain those clearances. Set `REAR_BATTERY_SLOT_ENABLED = False`
to restore the original footprint or use rear-wall fans.

Validation checks the actual closed-case containment of the battery, plugs,
straps and cable exit, seated clearance with the lid on, loading with the lid
and attached fan removed, post/mount keepouts and manifold geometry. The
dimension PDF includes the internal-bay drawing and all configuration values.
