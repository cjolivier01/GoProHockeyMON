The rear fan mount supports independent horizontal and vertical angles from
−45° to +45°. Both default to 0°, which produces the original shell geometry.

```bash
blender --python gopro_fan_case_parametric_blender.py -- \
  --fan-angle-horizontal 30 --fan-angle-vertical -20
```

In Blender's Text Editor, edit `FAN_ANGLE_HORIZONTAL_DEG` and
`FAN_ANGLE_VERTICAL_DEG` in the script's CONFIG section. Command-line values
override those settings; Blender options go before `--` and script options
after it. Run with `-- --help` to see the angle arguments.

| Setting | Positive direction | Negative direction |
| --- | --- | --- |
| `--fan-angle-horizontal` | +X, right when looking at the rear | −X, left |
| `--fan-angle-vertical` | +Z, up | −Z, down |

The outward fan axis starts along −Y. Each angle is measured in its respective
X/Y or Z/Y projection: its direction is
`normalize((tan(horizontal), -1, tan(vertical)))`. Combining +45° on both axes
therefore produces a 54.74° total tilt. There is no extra roll.

Both faces of the mounting square rotate together. The pad keeps its configured
thickness, and its four through-bores and inner screw bosses follow the same
rotation. The dome bends into the fixed front socket; the camera contact faces,
sleeve joint, and perimeter fastener seats retain their original positions.
The optional fan adapter follows the pad. Its separate STL still uses the
original flange-down orientation, and fan-size/offset settings stay local to it.

Install the fan or adapter screws **from inside the open case**, before fitting
the sleeve. The holes pass through the pad. The checks include clearance for
5.5 mm diameter, 2.5 mm tall screw heads; measure your chosen hardware.
Steep angles can require a compact angled driver because the front rim limits
a straight screwdriver's approach. Source captive nuts use the same settings
at every angle and require sufficient flange thickness (4.5 mm with the default
nut chamber).

The acoustic baffle has been removed from the default case, including its
retaining tabs, tray, lid, gasket, and generated STLs. The cavity is open.
Angled configurations add rearward and sideways projection. Nonzero angles
require `BACK_DOME_ENABLED = True`.

The previews below show the bare back from both sides, including the 15°
horizontal setting. Each option builds and validates the complete assembly.
The inside images are mounting-face close-ups, with the camera inside the
cavity so the foreground rim does not hide the holes. Each row also links to
a whole-cavity view. The larger corner blocks are camera stops.

| Horizontal / vertical | Outside | Inside mounting face |
| --- | --- | --- |
| 0° / 0° | ![Straight outside](renderings/fan_angle_straight_outside.png) | ![Straight inside](renderings/fan_angle_straight_mount_inside.png) [Whole cavity](renderings/fan_angle_straight_inside.png) |
| +15° / 0° | ![15 degrees outside](renderings/fan_angle_right_15_outside.png) | ![15 degrees inside](renderings/fan_angle_right_15_mount_inside.png) [Whole cavity](renderings/fan_angle_right_15_inside.png) |
| −45° / 0° | ![Left outside](renderings/fan_angle_left_45_outside.png) | ![Left inside](renderings/fan_angle_left_45_mount_inside.png) [Whole cavity](renderings/fan_angle_left_45_inside.png) |
| +45° / 0° | ![Right outside](renderings/fan_angle_right_45_outside.png) | ![Right inside](renderings/fan_angle_right_45_mount_inside.png) [Whole cavity](renderings/fan_angle_right_45_inside.png) |
| 0° / −45° | ![Down outside](renderings/fan_angle_down_45_outside.png) | ![Down inside](renderings/fan_angle_down_45_mount_inside.png) [Whole cavity](renderings/fan_angle_down_45_inside.png) |
| 0° / +45° | ![Up outside](renderings/fan_angle_up_45_outside.png) | ![Up inside](renderings/fan_angle_up_45_mount_inside.png) [Whole cavity](renderings/fan_angle_up_45_inside.png) |
| +30° / −20° | ![Compound outside](renderings/fan_angle_right_30_down_20_outside.png) | ![Compound inside](renderings/fan_angle_right_30_down_20_mount_inside.png) [Whole cavity](renderings/fan_angle_right_30_down_20_inside.png) |
| +45° / +45° | ![Maximum compound outside](renderings/fan_angle_right_45_up_45_outside.png) | ![Maximum compound inside](renderings/fan_angle_right_45_up_45_mount_inside.png) [Whole cavity](renderings/fan_angle_right_45_up_45_inside.png) |

The default 60 mm adapter mounted at +30° horizontal and −20° vertical:

![Angled rear adapter assembled](renderings/fan_angle_adapter_assembled.png)

From the repository root, run the regression checks and regenerate the images:

```bash
blender --background --factory-startup --threads 8 --python-exit-code 1 \
  --python models3d/fan-case/check_fan_angles.py
blender --background --factory-startup --threads 8 --python-exit-code 1 \
  --python models3d/fan-case/render_fan_angle_previews.py
```

The checks cover CLI limits and invalid values, small and maximum angles,
all four compound limits, both mounting faces, pad thickness, through-bores,
inside screw-head clearance, wall material, perimeter screw access, TPU/rigid
backs, adapter clearance, absence of baffle parts and tabs, STL reimport, and
adapter print-bed placement.
