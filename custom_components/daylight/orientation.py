"""Clear-sky receiving-plane estimate from horizontal and direct spectra.

The direct beam uses geometric incidence. The diffuse sky uses the isotropic
projection and ground reflection uses the fixed 0.2 albedo of the reference.
This is an approximation for non-horizontal planes, not a directional-sky run.
"""

import json
import math
from bisect import bisect_right
from functools import lru_cache
from pathlib import Path

from .model import chromaticity, color_temperature, from_elevation, load_table, number

DEFAULT_OPTIONS = {"tilt": 0, "facing_mode": "fixed", "bearing": 90}
FACING_MODES = ("fixed", "follow_sun")
GROUND_ALBEDO = 0.2


def validate_options(options):
    """Return a complete, validated receiver configuration."""
    tilt = number(options.get("tilt", 0), "tilt", 0, 90)
    bearing = number(options.get("bearing", 90), "bearing", 0, 359)
    mode = options.get("facing_mode", "fixed")
    if mode not in FACING_MODES:
        raise ValueError("facing_mode must be fixed or follow_sun")
    return {"tilt": tilt, "facing_mode": mode, "bearing": bearing}


@lru_cache(maxsize=1)
def _direct_nodes():
    return json.loads(Path(__file__).with_name("direct_reference.json").read_text())["nodes"]


def _direct_normal(elevation):
    if elevation <= 0:
        return [0.0, 0.0, 0.0], 0.0
    nodes = _direct_nodes()
    angles = [row["elevation"] for row in nodes]
    index = max(0, min(len(nodes) - 2, bisect_right(angles, elevation) - 1))
    low, high = nodes[index : index + 2]
    fraction = max(
        0.0,
        min(1.0, (elevation - low["elevation"]) / (high["elevation"] - low["elevation"])),
    )
    xyz = [(1 - fraction) * a + fraction * b for a, b in zip(low["xyz"], high["xyz"], strict=True)]
    edi = (1 - fraction) * low["melanopic_edi"] + fraction * high["melanopic_edi"]
    return xyz, edi


def oriented_daylight(elevation, azimuth, tilt, facing_mode, bearing):
    """Evaluate incident daylight on an upward-facing tilted receiver."""
    options = validate_options({"tilt": tilt, "facing_mode": facing_mode, "bearing": bearing})
    base = from_elevation(elevation)
    elevation = base["geometric_elevation"]
    azimuth = number(azimuth, "azimuth", 0, 360)
    tilt = options["tilt"]
    bearing = azimuth if options["facing_mode"] == "follow_sun" else options["bearing"]
    e, beta, relative = map(math.radians, (elevation, tilt, azimuth - bearing))
    incidence = max(
        0.0, math.sin(e) * math.cos(beta) + math.cos(e) * math.sin(beta) * math.cos(relative)
    )
    if elevation < 0:
        incidence = 0.0
    direct_xyz, direct_edi = _direct_normal(elevation)
    direct_lux = 683 * direct_xyz[1] * incidence
    result = {
        **base,
        "receiver_tilt": tilt,
        "receiver_facing_mode": options["facing_mode"],
        "receiver_bearing": bearing,
        "direct_lux": direct_lux,
        "orientation_model": "horizontal_reference" if tilt == 0 else "isotropic_sky_estimate",
    }
    if tilt == 0:
        return result
    horizontal_direct = math.sin(e) if elevation >= 0 else 0.0
    sky_factor = (1 + math.cos(beta)) / 2
    ground_factor = GROUND_ALBEDO * (1 - math.cos(beta)) / 2
    if base["xyz"] is None:
        result.update(
            lux=base["lux"] * (sky_factor + ground_factor), quality="estimated_orientation"
        )
        return result
    xyz = [
        max(0.0, total - normal * horizontal_direct) * sky_factor
        + total * ground_factor
        + normal * incidence
        for total, normal in zip(base["xyz"], direct_xyz, strict=True)
    ]
    xy, uv = chromaticity(xyz)
    cct, duv = color_temperature(uv, load_table()["planckian_locus"]) if uv else (None, None)
    if base["cct_kelvin"] is None:
        cct = None
    edi = base["melanopic_edi"]
    if edi is not None:
        edi = (
            max(0.0, edi - direct_edi * horizontal_direct) * sky_factor
            + edi * ground_factor
            + direct_edi * incidence
        )
    result.update(
        lux=683 * xyz[1],
        melanopic_edi=edi,
        cct_kelvin=cct,
        xyz=xyz,
        xy=xy,
        duv=duv,
        quality="estimated_orientation",
        cct_reason=(
            None if cct is not None else base["cct_reason"] or "outside_cct_reporting_range"
        ),
    )
    return result
