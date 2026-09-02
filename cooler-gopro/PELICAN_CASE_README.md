# Pelican Case Parametric Generator

This Blender Python script generates a complete Pelican/Storm hard case model programmatically, based on the dimensions from `pelican-case.stl`.

## Overview

The script creates a fully parametric hard case with:
- **Case base** with reinforced walls and bottom
- **Lid** with integrated closure system  
- **TPU gasket seal** for weather resistance
- **Latches** (3x front-mounted)
- **Hinges** (3x rear-mounted barrel hinges)
- **Carrying handle** on lid

## Generated Files

Running the script produces:

1. **pelican_case_body_PLA_PETG.3mf** - Main case body and lid
   - Print with: PLA or PETG
   - Recommended: PETG for better durability and temperature resistance
   
2. **pelican_case_hardware_PETG_HF.3mf** - Latches, hinges, and handle
   - Print with: PETG-HF (High Flow) or PETG
   - These parts need strength and wear resistance
   
3. **pelican_case_seal_TPU.3mf** - Gasket seal
   - Print with: TPU (flexible filament)
   - Shore hardness: 95A recommended
   
4. **pelican_case_complete_assembly.3mf** - Complete assembly for reference
   - Shows how all parts fit together
   
5. **pelican_case_parametric.blend** - Editable Blender file
   - Modify parameters and regenerate

## Dimensions

Based on analyzed STL file:
- **Width**: 346.71 mm
- **Depth**: 153.06 mm  
- **Height**: 345.54 mm
- **Wall thickness**: 3.0 mm
- **Bottom thickness**: 4.0 mm

## Usage

### Run the Generator

```bash
~/Apps/Blender/blender --background --python generate_pelican_case.py
```

### Customize Parameters

Edit the PARAMETERS section in `generate_pelican_case.py`:

```python
# Overall case dimensions (mm)
CASE_WIDTH = 346.71
CASE_DEPTH = 153.06
CASE_HEIGHT = 345.54

# Wall thickness
WALL_THICKNESS = 3.0
LID_THICKNESS = 3.0
BOTTOM_THICKNESS = 4.0

# Latch dimensions
LATCH_WIDTH = 25.0
LATCH_HEIGHT = 40.0
LATCH_DEPTH = 15.0

# Handle dimensions
HANDLE_WIDTH = 120.0
HANDLE_HEIGHT = 80.0
HANDLE_GRIP_DIAMETER = 25.0

# Corner radius
CORNER_RADIUS = 8.0
```

### 3D Printing Recommendations

#### Case Body (PLA/PETG)
- **Layer height**: 0.2-0.3mm
- **Infill**: 20-30%
- **Perimeters**: 3-4
- **Top/Bottom layers**: 5-6
- **Supports**: Minimal, if needed for lip overhang
- **Print time**: ~24-36 hours (depending on printer)

#### Hardware (PETG-HF)
- **Layer height**: 0.15-0.2mm
- **Infill**: 50-100% (these are structural)
- **Perimeters**: 4-5
- **Supports**: Yes, for latch hooks
- **Print orientation**: Hinges vertical, latches with hooks pointing up
- **Print time**: ~6-10 hours total

#### Seal (TPU)
- **Layer height**: 0.2mm
- **Infill**: 20-30%
- **Perimeters**: 3
- **Speed**: Slow (20-30 mm/s)
- **Retraction**: Minimal or disabled
- **Print time**: ~2-4 hours

### Assembly

1. Print all parts according to specifications
2. Clean up any support material and brims
3. Test fit all parts before final assembly
4. Install hinges on back edge (use small screws or epoxy)
5. Install latches on front (ensure proper alignment)
6. Press TPU seal into groove on case base lip
7. Test lid closure - should compress seal evenly
8. Attach handle to lid top (screws or through-bolts)

### Post-Processing

- **Smoothing**: Sand with 220-400 grit for better finish
- **Sealing**: Apply epoxy or polyurethane coating for water resistance
- **Hardware**: Add metal pins through hinge barrels for strength
- **Padding**: Add foam insert inside for equipment protection

## Script Features

### Material Assignment
The script automatically assigns materials for multi-material printing:
- Dark grey for case body (PLA/PETG)
- Black for seal (TPU)
- Light grey for hardware (PETG-HF)

### Collection Organization
Parts are organized in Blender collections by material:
- `Case_PLA_PETG` - Body and lid
- `Hardware_PETG_HF` - Latches, hinges, handle
- `Seal_TPU` - Gasket seal

### Modifiers
The script uses:
- **Bevel modifier** for rounded corners
- **Boolean modifier** for creating hollow shells
- **Array modifier** (potential) for multiple latches/hinges

## Customization Ideas

### Make it Smaller/Larger
Adjust `CASE_WIDTH`, `CASE_DEPTH`, `CASE_HEIGHT` proportionally.

### Add More Latches
Modify the `create_latches()` function to add positions.

### Different Handle Style
Replace `create_handle()` with custom design (e.g., recessed, folding).

### Add Mounting Points
Add screw bosses or threaded inserts for accessories.

### Reinforcement Ribs
Add internal ribs for extra strength in large cases.

## Technical Notes

### Blender Version
- Tested with: Blender 5.2.0 LTS
- Uses modern API: `bpy.ops.wm.stl_import()` instead of deprecated `import_mesh.stl()`

### Manifold Geometry
The original STL had 27 non-manifold edges. This parametric version creates clean, manifold geometry suitable for 3D printing.

### Export Format
3MF format is used because it:
- Preserves units (mm)
- Supports multiple objects
- Maintains material assignments
- Compatible with all major slicers (PrusaSlicer, Cura, OrcaSlicer, Bambu Studio)

## Troubleshooting

### "No module named bpy"
Run script through Blender's Python, not system Python:
```bash
~/Apps/Blender/blender --background --python generate_pelican_case.py
```

### Parts don't fit together
- Check printer calibration (print calibration cube)
- Add tolerance gaps in parameters (e.g., reduce lid dimensions by 0.2mm)
- Verify seal compression - should be snug but not too tight

### TPU seal won't print well
- Reduce speed to 20 mm/s
- Disable retraction or set very short
- Use direct drive extruder (not Bowden)
- Increase nozzle temperature 5-10°C

### Case warps during printing
- Use brim or raft
- Ensure good bed adhesion
- Use enclosure for PLA/PETG
- Consider splitting large case into smaller parts

## License

This parametric model is based on the original `pelican-case.stl` design. Modify and use as needed for your projects.

## Contact

For issues or questions about this generator script, refer to the main project documentation.
