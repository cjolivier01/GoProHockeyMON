# Expanded Mission 1 alternate case

The expanded case carries the existing two complete fan-case camera assemblies,
small fan cables, batteries and battery doors, plus the assembled goalpost mount,
three custom remotes, two OEM backup remotes, and a large rolled cord. It replaces the compact case and inserts.
The stronger latch, handle hardware, and 3.8 mm hinge-rod fit remain in use.

Both lids carry **Sports AI** in the same embedded Neuropol font style, with
the orange inlay and hockey artwork.

![Sports AI lid artwork](renderings/mission1_sports_ai_lid.png)

The default generator produces this kit:

```sh
make -C models3d mission1-field-case
make -C models3d mission1-field-case-plate-overview
```

The project contains **15 unique STLs on 10 plates**, including rigid and 68D TPU
lid alternatives. Select one lid. The compact dual-fan inserts are a separate
profile, available with `make -C models3d mission1-field-case-compact`; they are
not part of this expanded packing arrangement. Their separate exports go into
`mission1-field-case/compact/`, retaining the previous case dimensions and kit.

## Dimensions and print fit

| Dimension | Expanded case |
| --- | ---: |
| Main shell width × depth × bottom-to-rim height | 234 × 180 × 160 mm |
| Internal width × depth × floor-to-rim height | 225 × 171 × 156.8 mm |
| Base printed envelope, including projections | approximately 241.6 × 209.8 × 165 mm |
| Lid printed envelope | approximately 244 × 207.8 × 16 mm |
| Closed case height, bottom to lid top | 171 mm |

Every printed part fits within 250 × 250 mm and below 250 mm tall. The 3MF turns
both shell and compound lid plates by 90° in plan so they also clear the
printer's 18 × 28 mm excluded corner. Keep this placement when slicing. The
standalone shell/lid STLs may need the same rotation on a printer with that
corner exclusion. Check any brim or skirt against the remaining bed margin.

Case depth and height were increased with explicit authorization for this
loadout. Camera and fan locations, outward fan angles, cable routes, and the
positions of the batteries and PWM plugs are preserved. The door slots keep
their horizontal positions; their floors now sit at 13.8 mm above the insert
underside, raising each door by 10.8 mm. Their 24.8 mm front rims match the
adjacent battery-pocket rims, with 11 mm seating depth and 7 mm of door exposed
for removal. This change requires reprinting only the lower TPU insert; the
case bottom, camera seats, battery pockets, trays and lids are unchanged.

That same lower insert now extends only the back edge of each rectangular
fan-inlet slot **1.5 mm farther outward along its handed ±15-degree fan axis**.
It accepts a fan 1.5 mm deeper than the nominal 20 mm reference without
flexing the insert during loading. Slot width and side walls, camera seats,
loadout positions, and all case internal and external dimensions remain
unchanged.

![Raised battery-door pockets](renderings/mission1_raised_battery_door_pockets.png)

![Rear fan depth clearance](renderings/mission1_fan_rear_clearance.png)

The lower insert extends to the new shell walls and retains the bearing webs
for the tray stack.
The PWM insertion corridors are cut after the final guide/web unions so those
unions cannot close the plug channels.

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
and the mount tray for its matching air channels. The shell, flat lid, lid pad
and lower inserts keep their existing geometry. The full Ø154 × 42 mm cord bay
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
replacement flat lid pad uses **85A TPU**; select the actual filament profile for
its separate plate. The optional snap lid and calibration coupon require the
specified 68D material, not the 85A pad filament. The project uses a generic TPU
preset, which does not itself encode Shore hardness.

The enlarged base, lid, gasket, pad and insert set require new prints. The
separate latch parts, handle, 151 mm-long 3.8 mm hinge rod, and hinge coupon retain
their prior dimensions. Use the existing M3 latch and M3 × 14 handle hardware.
The hinge openings remain 4.325 mm in the base, 4.55 mm at the lid receiver and
4.4 mm at the rigid slot. The optional snap throat is now 3.5 mm, giving 0.3 mm diametral interference
with the 3.8 mm rod (previously 0.2 mm). Its straight section is 1.55 mm long,
leaving approximately 0.096 mm of flat throat beyond the round receiver before
the smooth 0.8 mm lead-in. The four coupon banks use this same updated entrance;
one dot is the nominal 3.5 mm, followed by 3.6/3.7/3.8 mm.

The latch-bearing lip is now **3.2 mm thick on the rigid lid** and **4.0 mm on
the 68D TPU lid**, increased from 2.4 mm. Added material sits below the existing
bearing surface and continues into its back-wall reinforcement. Latch take-up,
rail position, case dimensions and storage clearances are unchanged. These are
lid-only refinements; existing base, latch, handle and inserts remain compatible.
The hinge change tightens nominal snap interference; retention force depends
on the printed material. The optional lid still uses 68D TPU; the separate
2 mm lid pad remains 85A TPU.

![Lid lip thickness comparison](renderings/mission1_lid_lip_thickness.png)

![TPU hinge snap comparison](renderings/mission1_tpu_hinge_snap_comparison.png)

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
