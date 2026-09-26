"""Receiver orientation must preserve horizontal behavior and solar geometry."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.daylight.orientation import oriented_daylight
from custom_components.daylight.preview import daily_curve, render_svg


def test_horizontal_equals_reference_at_any_bearing():
    from custom_components.daylight.model import from_elevation

    reference = from_elevation(35)
    for bearing in (0, 90, 180, 270):
        got = oriented_daylight(35, 120, 0, "fixed", bearing)
        assert got["lux"] == pytest.approx(reference["lux"])
        assert got["melanopic_edi"] == pytest.approx(reference["melanopic_edi"])
        assert got["cct_kelvin"] == pytest.approx(reference["cct_kelvin"])


def test_sun_behind_vertical_receiver_has_no_direct_component():
    east = oriented_daylight(30, 90, 90, "fixed", 90)
    west = oriented_daylight(30, 90, 90, "fixed", 270)
    assert east["direct_lux"] > 0
    assert west["direct_lux"] == 0
    assert east["lux"] > west["lux"]


def test_following_sun_ignores_saved_bearing():
    a = oriented_daylight(30, 90, 90, "follow_sun", 0)
    b = oriented_daylight(30, 90, 90, "follow_sun", 180)
    assert a["lux"] == pytest.approx(b["lux"])


def test_unresolved_twilight_does_not_invent_color_or_melanopic_edi():
    result = oriented_daylight(-12, 90, 90, "fixed", 90)
    assert result["lux"] > 0
    assert result["melanopic_edi"] is None
    assert result["cct_kelvin"] is None


def test_direct_sun_is_zero_at_horizon():
    result = oriented_daylight(0, 90, 90, "fixed", 90)
    assert result["direct_lux"] == 0


def test_daily_preview_spans_local_day_and_is_an_svg():
    curve = daily_curve(
        40.7,
        -74.0,
        "America/New_York",
        datetime(2026, 9, 26, tzinfo=ZoneInfo("America/New_York")).date(),
        {"tilt": 90, "facing_mode": "fixed", "bearing": 90},
    )
    assert curve[0]["time"].hour == 0
    assert curve[-1]["time"].hour == 0
    assert curve[-1]["time"].day == 27
    assert any(row["lux"] > 0 for row in curve)
    svg = render_svg(curve)
    assert svg.startswith("<svg")
    assert "Illuminance" in svg
    assert "Melanopic EDI" in svg
    assert "Color temperature" in svg
