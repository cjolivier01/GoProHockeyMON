"""Shared square-fan reference dimensions for parametric Blender generators.

The supported set matches the Noctua-based sizes historically carried by
``dual_fan_parametric_blender.py``.  Values are millimeters.  ``opening`` and
``hub`` describe the nominal unobstructed fan face used by acoustic/grille
geometry; individual products should still be measured before fabrication.
"""

from __future__ import annotations


STANDARD_FAN_PRESETS = {
    40: {
        "frame": 40.0,
        "depth": 20.0,
        "hole_spacing": 32.0,
        "hole_diameter": 4.3,
        "opening": 36.0,
        "hub": 20.0,
        "reference": "Noctua NF-A4x20",
    },
    60: {
        "frame": 60.0,
        "depth": 25.0,
        "hole_spacing": 50.0,
        "hole_diameter": 4.3,
        "opening": 55.0,
        "hub": 28.0,
        "reference": "Noctua NF-A6x25",
    },
    80: {
        "frame": 80.0,
        "depth": 25.0,
        "hole_spacing": 71.5,
        "hole_diameter": 4.3,
        "opening": 75.0,
        "hub": 36.0,
        "reference": "Noctua NF-A8",
    },
    120: {
        "frame": 120.0,
        "depth": 25.0,
        "hole_spacing": 105.0,
        "hole_diameter": 4.3,
        "opening": 110.0,
        "hub": 50.0,
        "reference": "Noctua NF-A12x25",
    },
}

# Manufacturer reference pages used for the shared dimensional set:
# https://www.noctua.at/en/products/nf-a4x20-pwm/specifications
# https://www.noctua.at/en/products/nf-a6x25-pwm/specifications
# https://www.noctua.at/en/products/nf-a8-pwm/specifications
# https://www.noctua.at/en/products/nf-a12x25-pwm/specifications


def get_standard_fan_preset(size_mm: int | float):
    """Return a copy of one preset or raise a useful unsupported-size error."""
    try:
        numeric_size = float(size_mm)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Fan size must be numeric; got {size_mm!r}") from error
    if isinstance(size_mm, bool) or not numeric_size.is_integer():
        raise ValueError(f"Fan size must be a whole millimeter value; got {size_mm!r}")
    size = int(numeric_size)
    try:
        return dict(STANDARD_FAN_PRESETS[size])
    except KeyError as error:
        choices = ", ".join(str(value) for value in sorted(STANDARD_FAN_PRESETS))
        raise ValueError(
            f"Unsupported fan size {size_mm!r}; choose {choices} mm"
        ) from error
