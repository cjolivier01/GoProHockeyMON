# Expanded Mission 1 alternate case

The expanded case carries the existing two complete fan-case camera assemblies,
small fan cables, batteries and battery doors, plus the assembled goalpost mount,
three custom remotes, two OEM backup remotes, and a large rolled cord. It replaces the compact case and inserts.
The stronger latch, handle hardware, and 3.8 mm hinge-rod fit remain in use.

The shell exterior follows the supplied `build_hardcase.py`: **25 mm plan-view
corners**, a rounded bottom blending over 30 mm with a 14 mm inset, narrower
**6 × 6 mm impact ribs**, and a matching 5 mm bumper on the front and sides of
the parting rim. The rear bumper is relieved for the existing hinge sweep, and
three full-width buttresses rise from 20 mm above the floor into the base hinge
barrels, following the reference hardcase's long rear load paths.
Both lids have a **24 mm raised, curved shoulder** above the original latch
and hinge line. Their 6 mm-wide guards ramp into the shoulder and end at the
parting rim; local pockets in the base guards clear the reinforced latch lips.

![Rounded exterior](renderings/mission1_hardcase_front.png)

![Rear hinge and rounded base](renderings/mission1_hardcase_rear.png)

![Full-width base hinge buttresses](renderings/mission1_hardcase_base_hinge_buttresses.png)

![Supplied hardcase reference](renderings/mission1_hardcase_reference.png)

The reference's shape is adapted to the existing 250 mm print bed and equipment
stack. It retains the Sports AI inlay, two-piece latches, M3 latch/handle screws
and existing 3.8 mm hinge rod. The reference uses interleaved knuckles and axial
pins; this revision retains the calibrated removable rigid/68D hinge options.

```sh
make -C models3d mission1-field-case
make -C models3d mission1-field-case-plate-overview
```

The project contains **15 unique STLs on 10 plates**, including rigid and 68D TPU
lid alternatives. Select one lid. The compact dual-fan kit remains separately
available with `make -C models3d mission1-field-case-compact`; its exports go in
`mission1-field-case/compact/`. It retains its original corner radius and lid
height, with the narrower ribs, rim guards and supported tray rails.

## Dimensions and print fit

| Dimension | Expanded case |
| --- | ---: |
| Main shell width × depth × bottom-to-rim height | 234 × 180 × 160 mm |
| Nominal internal width × depth × floor-to-rim height | 225 × 171 × 156.8 mm |
| Base printed envelope, including projections | 246 × 209.8 × 165 mm |
| Rigid lid printed envelope | 244 × 207.8 × 39.8 mm |
| TPU lid printed envelope | 244 × 209.44 × 39.64 mm |
| Closed case height, bottom to lid top | 195 mm |
| Equipment contact face in closed lid | Z = 165 mm |

The nominal cavity dimensions are preserved; the rounded floor and corners
reduce space locally. The lower insert uses an inward 45° ramp inside that curved floor, and the
mount tray, front bin and remote organizer have matching rounded corners.
Camera, battery, door, cable, mount, cord and remote positions are retained.
The 2 mm TPU lid contact plate gains a 24 mm open spacer with a perimeter frame
and two crossing ribs. Its contact face remains at the existing packing plane.
Bond the spacer rim and ribs to the inside roof with a suitable TPU-compatible
adhesive. The asymmetrical key determines its orientation.

**Reprint the base, selected lid with its gasket, lower insert, mount tray,
front bin, remote organizer, lid pad, both latch levers, both hooks and handle
as a matching set.** The 151 mm hinge rod can be reused. Reprint the TPU hinge
coupon for its tilted entrance. The rounded inserts need the revised shell fit;
retain the previous files if you want to reproduce the previous case.

Every part fits within 250 × 250 mm and below 250 mm tall. The project turns the
base and compound lids 90° in plan to clear the printer's excluded corner.
Keep this placement and check any brim against the remaining bed margin.
Print the base upright, the lid crown-down and the pad contact-face-down with
its spacer upward. Exterior ramps stay within 45°; the latch bays and hinge
receivers retain short bridges. The project uses 0.20 mm layers with supports disabled. Bridge
quality and physical fit still require a printed check with your material.

![Latch and rim detail](renderings/mission1_hardcase_rim.png)

The existing raised battery-door pockets, deeper rear fan-inlet reliefs, cable
corridors and load-bearing insert webs remain in use inside the reshaped liner.

## What fits

| Item | Supplied measurement | Reserved envelope |
| --- | --- | --- |
| Assembled mount | Photo suggests approximately 205 × 140 mm; maximum depth 35 mm | 210 × 146 × 37 mm |
| Rolled cord | Approximately Ø150 × 40 mm | Ø154 × 42 mm |
| Three custom remotes | 37.5 × 45.5 × 14.5 mm body, plus 1.5 mm side buttons | Upright: 14.5 × 45.5 × 39 mm, button edge up |
| Two OEM GoPro remotes | 66 × 40 × 19 mm | Upright: 19 × 66 × 40 mm, assuming measurements include buttons |

The mount dimensions are estimates from the photographed ruler, not a precision
scan. It fits assembled as shown within the reserved envelope; tuck the tether
inside that envelope. The cord allowance accepts modest winding variation; a
looser bundle larger than Ø154 × 42 mm needs recoiling.

The entire organizer is now **one piece of TPU-85A**, including five integral
remote slots. Its outer envelope remains **223 × 169 × 46.3 mm**, with the
3 mm main floor, rear key notch and stack bearings. Local air passages
under the front/rear edges leave at least 2 mm of floor above their roofs. The right-hand strip
contains a continuous molded pocket block, bonded to the floor, cord divider
and outside wall. Reprint this organizer for the remote slots and channels,
and the mount tray for its matching air channels. The remote slot geometry is
retained in the organizer with rounded outer corners. The full Ø154 × 42 mm cord bay
remains available.

### Remote slots and button clearance

Each pocket is **26 mm deep**, with **0.30 mm clearance per side** around the
body and two small squeeze nubs on the plain short ends. Each nub projects
**0.20 mm into the nominal body envelope** over an 8 × 3 mm patch. These local
nubs provide soft friction; the surrounding deep walls provide side support,
as with the battery pockets in the lower fan-case insert. All five pockets
have continuous guides along both sides. The outside finger scallops stop at
the pocket rims so they do not remove the support below them.

The three custom remotes stand with their 37.5 mm body axis vertical and their
1.5 mm side-button projection pointing upward, entirely above the pocket rims.
The two OEM controls stand with the 40 mm axis vertical and the 66 mm axis
along the tray. **All screen/front faces point toward +X, the right-hand
outside wall, away from the cord bay.** Load and remove each remote vertically.
Recessed `FACE >` and `BUTTON EDGE UP` legends mark the orientation.

Each OEM pocket has an upward-open **3 mm front-button clearance zone over the
central 54 mm** of its 66 mm length. The remaining **6 mm band at each short
end of the front face** acts as a full-depth casing guide, providing support
against sideways tipping without filling the central button area.

**The OEM button layout has not yet been measured.** This design assumes the
66 × 40 × 19 mm measurement includes the buttons, that side buttons face
upward, and that the bottom, short-end grip patches and 6 mm front-edge casing
bands are plain. Confirm those areas on the physical controls; button relief
must be extended or moved if necessary. The renderings show measured envelopes,
not detailed button CAD. Retention force and TPU deflection need a printed fit
check. The modeled pocket clearance is not a prediction of printed tolerance.

Checks reserve **2 mm above and around the upward button edge**, plus the OEM
front clearance described above. Seated and continuous vertical button sweeps
must clear the tray, shell and other accessories. With the existing 0.6 mm
stack allowance, actual closed-pad headroom is **4.4 mm above the custom button
envelopes and 3.4 mm above the OEM envelopes** (5 and 4 mm nominally).

The validation also requires 22 mm of uninterrupted side-guide material at
four casing corners per pocket. The body clears these guides when upright,
but contacts them when tilted **±2° about either horizontal axis**, excluding
the floor and grip nubs from that calculation. This checks geometric restraint;
soft-material stiffness and transport loads still require physical testing.
Only the ten designated nub contacts may overlap the remote bodies.

![One-piece tray with five deep slots](renderings/mission1_remote_slots.png)

![Five remotes and the unchanged cord bay](renderings/mission1_remote_tray_loaded.png)

![Straight loading orientation](renderings/mission1_remote_loading.png)

![OEM button air and closed-pad clearance](renderings/mission1_remote_button_clearance.png)

### Air channels for lifting the tray

Both the **TPU organizer** and the **rigid goalpost mount tray** have four
**5 mm-wide × 1 mm-deep outside grooves**: two on the front wall and two on the
rear wall, at X = ±80 mm. They let air reach beneath each tray as it is lifted,
including while it is fully seated on the supporting parts. Their positions
avoid the remote pockets, pull-cord eyes, grip notches, locating key and
established stack-bearing locations.

Each groove feeds two underside passages extending 5 mm inward across that
rim. Each passage is **2 mm wide × 1 mm high**, with a **45° pitched roof**.
The pair leaves a 1 mm central bearing rib. At least **2 mm of wall and floor**
remains around the channels. The storage compartments stay closed at the
bottom. The organizer remains **223 × 169 × 46.3 mm**; the goalpost tray remains
**223 × 169 × 42.03 mm**, with its original **217 × 163 mm** inner footprint and
the same **210 × 146 × 37 mm** mount clearance envelope. The mount tray remains
rigid material; the organizer remains TPU-85A.

Solid air probes check **eight continuous routes per tray**, against the case
and the actual supporting parts: the mount tray beneath the organizer, and
the lower insert and utility bin beneath the mount tray. Separate material
probes check the remaining wall, floor and central ribs. Existing stack-bearing
checks still apply. These prove open geometric routes; suction reduction and
deformation of printed material remain physical tests. Cyan arrows illustrate
the air paths.

![Front air channels](renderings/mission1_air_channels_overview.png)

![Rear air channels](renderings/mission1_air_channels_rear.png)

![Underside air passages](renderings/mission1_air_channels_underside.png)

![Air path through the seated tray stack](renderings/mission1_air_channels_seated_section.png)

![Pitched underside passages](renderings/mission1_air_channels_underside_detail.png)

![Goalpost tray front channels](renderings/mission1_mount_air_channels_overview.png)

![Goalpost tray rear channels](renderings/mission1_mount_air_channels_rear.png)

![Goalpost tray underside](renderings/mission1_mount_air_channels_underside.png)

![Air below the seated goalpost tray](renderings/mission1_mount_air_channels_seated_section.png)

![Goalpost tray pitched passages](renderings/mission1_mount_air_channels_underside_detail.png)

## Packing and retained storage

Pack from the bottom upward:

1. Seat the lower TPU insert and the existing complete camera/fan assemblies,
   small cables, batteries, doors, and PWM plugs.
2. Fit the lower front utility bin. It retains approximately **217 × 37.5 ×
   24.7 mm** of usable storage beneath the mount tray.
3. Fit the rigid mount tray and lay the assembled mount flat inside it. The
   tray rests on the rear cradle ledges and the front utility bin's side walls.
4. Fit the one-piece TPU-85A upper organizer. Put the rolled cord in the large
   left bay. Load three custom remotes in the short front pockets and two OEM
   remotes in the longer rear pockets, in the orientation described above.
   Keep straps tucked clear of every button and within the available tray height.
5. Fit the 2 mm 85A TPU lid pad and close the lid. Keep the normal gasket.

To unpack, open the lid to 110°, lift out the loaded organizer, then the mount
tray, then the front bin. The trays are stacked; the front bin cannot lift out
through the mount tray. Fit four 2 mm cord pull loops through the mount tray’s
3.5 mm vertical eye holes, with stopper knots below the eyes. The eyes project
inward at the front and rear so the cords never run in the 1 mm gap between
tray and shell. Lift the front and rear together to keep the loaded tray level.
Tuck the loops entirely below the mount-tray rim, in the front and rear gaps
around the mount, before installing the organizer. Finger scallops provide
access after lifting a tray clear of the case. Both accessory trays have
3 mm main floors and outer walls; each tray's local air-channel relief
leaves at least 2 mm of floor and wall around each passage.

| Height above outside case bottom | Nominal height |
| --- | ---: |
| Highest seated camera/fan feature | 75.27 mm |
| Mount tray underside / front-bin rim | 75.97 mm |
| Mount tray inner floor | 78.97 mm |
| Top of conservative mount envelope | 115.97 mm |
| Upper organizer underside | 118.00 mm |
| Upper organizer inner floor | 121.00 mm |
| Remote seat on the organizer floor | 121.00 mm |
| Integral remote pocket rims | 147.00 mm |
| Top of custom button envelope | 160.00 mm |
| Top of OEM remote envelope | 161.00 mm |
| Top of conservative cord envelope | 163.00 mm |
| Upper organizer rim | 164.30 mm |
| Lid pad underside | 165.00 mm |
| Rigid lid inner face | 167.00 mm |

The lid pad has **0.7 mm clearance above the organizer rim**, with no intended
tray compression. The previous key clearance correction is carried into the
upper organizer. Its rear-rim notch follows the locating key to X = −42 mm,
Y = +82 mm; the notch is 14 × 8 mm and 3 mm deep. A 0.6 mm stack allowance still
leaves 0.1 mm pad clearance. This is a geometric allowance, not a prediction of
any particular printer's dimensional error.

![Closed stack section](renderings/mission1_expanded_closed_stack.png)

![Exploded packing arrangement](renderings/mission1_expanded_loadout_exploded.png)

## Printing and hardware

Use rigid PETG or another tough rigid filament for the shell, chosen rigid lid
and **mount tray** (`mission1_field_case_mount_tray.stl`). The mount tray stays
on rigid filament 1. Use 0.20 mm layers, at least four walls, and enough
bottom layers to make its 3 mm main floor solid. Its air passages have 45°
roofs and leave at least 2 mm of floor above them.

Print the entire **upper organizer**
(`mission1_field_case_accessory_organizer.stl`) floor down in **TPU-85A**, using
0.20 mm layers, four walls and a solid 3 mm main floor. Its dedicated plate is
labeled `Coil and Five Remote Slots - TPU 85A` and assigned to TPU filament 3.
Choose an actual TPU-85A profile; the generic project TPU preset does not encode
Shore hardness. The upward-open slots have no roofs and the small retention
nubs have rounded edges. The underside air passages use 45° roofs.
No support structures are intended. A diagnostic
0.20 mm slice checks support-free toolpaths; it is not calibrated printer G-code.
Reprint both the organizer and the mount tray for this revision. There is no
separate retainer STL or extra retainer plate; the complete project contains
15 unique STLs on 10 plates.

Use a suitable resilient TPU for the lower insert and front utility bin. The
raised-roof lid pad uses **85A TPU**; select the actual filament profile for
its separate plate. The optional snap lid and calibration coupon require the
specified 68D material, not the 85A pad filament. The project uses a generic TPU
preset, which does not itself encode Shore hardness.

The enlarged base, lid, gasket, pad and insert set require new prints. The
latest exterior hardware revision also requires the matching wide latch parts
and handle described below. The 151 mm-long 3.8 mm hinge rod retains its prior
dimensions. Reprint the updated hinge coupon with the optional TPU lid.
The hinge openings remain 4.325 mm in the base, 4.55 mm at the lid receiver and
4.4 mm at the rigid slot. The optional snap throat is now 3.5 mm, giving 0.3 mm diametral interference
with the 3.8 mm rod (previously 0.2 mm). Its straight section is 1.55 mm long,
leaving approximately 0.096 mm of flat throat beyond the round receiver before
the smooth 0.8 mm lead-in. The four coupon banks use this same updated entrance;
one dot is the nominal 3.5 mm, followed by 3.6/3.7/3.8 mm.
The TPU entrance and blunt jaws point upward at 45° in print orientation so
the upper jaw grows from the receiver roof instead of starting in midair.
Open the TPU lid about **25°** for progressive attachment/removal. The rigid
lid retains its horizontal slot and **70°** removal position. Both retain
the same rod axis and existing base. Check the coupon with the actual material.

The latch-bearing lip is now **3.2 mm thick on the rigid lid** and **4.0 mm on
the 68D TPU lid**, increased from 2.4 mm. Added material sits below the existing
bearing surface and continues into its back-wall reinforcement. Latch take-up,
rail position and storage contacts are retained. The rounded shell and liner
changes still require the reprints listed above; use the matching wide base,
lid, latch set and handle for the hardware revision. Snap force depends on the
printed material; the optional lid uses 68D TPU, and the framed 24 mm roof spacer
uses 85A TPU.

![Lid lip thickness comparison](renderings/mission1_lid_lip_thickness.png)

![Upward-facing TPU snap entrance](renderings/mission1_hardcase_tpu_hinge.png)

![Printable lower insert underside](renderings/mission1_hardcase_insert_underside.png)

## Wider latches and handle

The expanded case has **40.96 mm-wide latches**, twice the previous 20.48 mm,
and a **119.8 mm overall handle envelope**, about 20.8% wider than 99.2 mm.
The handle's solid grip is 115.6 mm wide with a 95.6 mm opening. Each complete
fork moves outward 10.3 mm; its original mount shape, wall thickness, bores,
and 18-to-24 mm transition are preserved. Latch centers remain at ±82 mm.
The enlarged guards remain 8.22 mm inside the case sides.

A **hard 1 mm minimum-clearance check covers continuous 360° handle rotation**
against both closed latch levers, hooks, and moving link rods. The generated
meshes have **1.02 mm minimum axial separation**, after including ±0.2 mm latch
and ±0.4 mm handle axial play. Rotation about the handle's pivot preserves
this lateral separation at every angle. Protection walls are excluded from
this constraint; the check does not rely on a guard stopping rotation.

The full project build runs this check before export.
`check_mission1_closed_latch_handle.py` rejects the colliding 124 mm handle,
a positive gap below 1 mm, interference due to axial play, and deliberately
colliding moving parts. The original fork geometry is also compared against
the widened forks. Normal 0–90° handle travel retains **3.31 mm vertical
separation** through all latch positions, with latch release, handle strength,
and Allen access independently checked.

Reprint the **base, chosen lid, both latch levers, both hooks, and handle** as a
matching set. The wider mounts are incompatible with the previous narrow
latches and handle. The case interior remains **225 × 171 mm**, with the same
156.8 mm floor-to-rim depth, so existing inserts, gasket, inlay and hinge parts
remain usable. The compact profile retains its original hardware and dimensions.

Each wide latch needs one **M3 × 50 socket-head screw**, one M3 hex nut, and a
**4 mm-diameter rod cut to 40.96 mm**. The 3.6 mm-deep head recess leaves a
2.4 mm guard floor and nominally 0.04 mm screw-tip projection with full nut
engagement. Reuse the handle's two **M3 × 14 screws and M3 nuts**.

![Before and after hardware](renderings/mission1_wide_hardware_comparison.png)

![Installed wide hardware](renderings/mission1_wide_hardware_installed.png)

![Raised handle clearance](renderings/mission1_wide_hardware_clearance.png)

Regenerate these views with `render_mission1_wide_hardware.py` in background
Blender. Run `check_mission1_wide_hardware.py` for width, interior preservation,
compact compatibility and collision-rejection checks, together with the existing
latch and handle regression scripts.

## Checks

![Generated print plates](renderings/mission1_field_case_all_print_plates.png)

Generation validates the actual lower camera/fan/cable/hardware loadout, tray
bearings, continuous air passages, cavity containment, accessory dimensions, button clearance, loaded
tray removal, both lid variants' closing paths, latch/handle mechanics, mesh
integrity and the complete 3MF. Reference envelopes are excluded from exports.

```sh
blender --background --factory-startup --threads 8 --python-exit-code 1 \
  --python models3d/mission1-field-case/check_mission1_expanded_storage.py
blender --background --factory-startup --threads 8 --python-exit-code 1 \
  --python models3d/mission1-field-case/check_mission1_alternate_closure.py
```

The accessory regression rejects a mount placed outside its assigned cavity,
an oversized button envelope, and a blocked cable bay. The dedicated slot check
rejects a missing nub, absent or shallow side walls, missing end guides that
allow tipping, a rib in the button air, unintended body contact, tray growth,
a missing spare envelope, a shifted remote, zero squeeze, and insufficient
button headroom below the lid pad:

```sh
blender --background --factory-startup --threads 8 --python-exit-code 1 \
  --python models3d/mission1-field-case/check_mission1_remote_slots.py
```

The air-channel regression rejects a blocked outside groove, a filled underside
passage, insufficient floor or wall material, and a missing central bearing rib
on either tray. It also rejects a utility-bin obstruction beneath the mount
tray. Supply a validated scene to reuse the unchanged lower insert; the case
and both vented trays are rebuilt from current source:

```sh
blender --background --factory-startup --threads 8 --python-exit-code 1 \
  --python models3d/mission1-field-case/check_mission1_air_channels.py \
  -- --scene /path/to/validated-field-case.blend
```

Render each tray's channels from five angles using `render_mission1_air_channels.py`
with `-- --scene /path/to/validated-field-case.blend`.

These are geometry checks against the stated body/button assumptions, not a
substitute for confirming the physical OEM button positions and printed fit.
The closure regression rejects the unnotched top tray, overly thick lid pads and a reversed pad notch.
Cached-scene runs may use `-- --scene /path/to/validated-field-case.blend`.

The focused lid regression checks both lip thicknesses, latch motion and hinge
closure, then rejects a lip cut back to 2.4 mm and a TPU opening widened to
3.6 mm:

```sh
blender --background --factory-startup --threads 8 --python-exit-code 1 \
  --python models3d/mission1-field-case/check_mission1_lid_lip_hinge.py
```

## Rebuilding and checking the rounded exterior

```sh
make -C models3d mission1-field-case
make -C models3d check-mission1-hardcase-exterior
make -C models3d mission1-field-case-plate-overview
make -C models3d mission1-field-case-dim-pdf
make -C models3d check-mission1-field-case-dim-pdf-sync
```

The normal build checks both lid closures and hinge sweeps, latch and handle
clearances, the complete packed loadout and removable trays, manifold meshes,
and the generated 3MF. The focused exterior check also rejects an unsupported
lid shelf and a spacer that cannot reach the roof. The new shell views come
from `render_mission1_hardcase_exterior.py`; pass `-- --review-round N` to label
an updated review set. The before view is the source at `a9d8807`, and the
reference view builds the supplied `build_hardcase.py` directly.
