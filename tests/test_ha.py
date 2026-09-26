"""Public HA config flow, service actions, entity lifecycle, and input validation."""

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def setup_entry(hass):
    entry = MockConfigEntry(domain="daylight", title="Daylight", unique_id="daylight", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_melanopic_sensor_and_actions_expose_the_same_unscaled_reference(hass):
    await setup_entry(hass)
    sensor = hass.states.get("sensor.daylight_melanopic_edi")
    assert sensor is not None
    assert sensor.attributes["unit_of_measurement"] == "lx"
    assert sensor.attributes["state_class"] == "measurement"
    a = await hass.services.async_call(
        "daylight",
        "from_elevation",
        {"geometric_elevation": 0},
        blocking=True,
        return_response=True,
    )
    b = await hass.services.async_call(
        "daylight",
        "from_level",
        {"daylight_level": 1, "noon_elevation": 0},
        blocking=True,
        return_response=True,
    )
    assert a["melanopic_edi"] == pytest.approx(1104, rel=0.01)
    assert b["melanopic_edi"] == pytest.approx(a["melanopic_edi"])
    assert "melanopic_edi_reason" in sensor.attributes


@pytest.mark.parametrize(
    "time,expected,reason",
    [
        ("2026-09-23T18:48:00Z", "unknown", "outside_numerically_resolved_table"),
        ("2026-09-23T20:00:00Z", "0.0", "no_solar_reference"),
    ],
)
async def test_melanopic_sensor_distinguishes_unresolved_twilight_from_night(
    hass, freezer, time, expected, reason
):
    hass.config.latitude = 0
    hass.config.longitude = 0
    freezer.move_to(time)
    await setup_entry(hass)
    sensor = hass.states.get("sensor.daylight_melanopic_edi")
    assert sensor.state == expected
    assert sensor.attributes["melanopic_edi_reason"] == reason


async def test_actions_return_independent_results_without_changing_sensors(hass):
    await setup_entry(hass)
    before = {s.entity_id: s.state for s in hass.states.async_all("sensor")}
    a = await hass.services.async_call(
        "daylight",
        "from_elevation",
        {"geometric_elevation": 20},
        blocking=True,
        return_response=True,
    )
    b = await hass.services.async_call(
        "daylight",
        "from_level",
        {"daylight_level": 1, "noon_elevation": 20},
        blocking=True,
        return_response=True,
    )
    assert a["lux"] == pytest.approx(b["lux"])
    assert a["cct_kelvin"] == pytest.approx(b["cct_kelvin"])
    assert {s.entity_id: s.state for s in hass.states.async_all("sensor")} == before
    with pytest.raises((ServiceValidationError, vol.Invalid)):
        await hass.services.async_call(
            "daylight", "from_level", {"daylight_level": 2}, blocking=True, return_response=True
        )


async def test_multiple_receiving_surfaces_can_be_configured(hass):
    entry = await setup_entry(hass)
    states = hass.states.async_all("sensor")
    assert len(states) == 6
    level = next(s for s in states if s.entity_id.endswith("_level"))
    assert 0 <= float(level.state) <= 1
    result = await hass.config_entries.flow.async_init("daylight", context={"source": "user"})
    assert result["type"] == "form"
    added = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Bedroom"})
    assert added["type"] == "create_entry"
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 12
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert len([s for s in hass.states.async_all("sensor") if s.state != "unavailable"]) == 6


async def test_config_flow_without_yaml_or_credentials(hass):
    result = await hass.config_entries.flow.async_init("daylight", context={"source": "user"})
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 6


async def test_default_level_uses_todays_noon_and_rejects_boolean(hass):
    await setup_entry(hass)
    peak = next(
        s for s in hass.states.async_all("sensor") if s.entity_id.endswith("_noon_solar_elevation")
    )
    a = await hass.services.async_call(
        "daylight", "from_level", {"daylight_level": 1}, blocking=True, return_response=True
    )
    assert a["geometric_elevation"] == pytest.approx(float(peak.state))
    with pytest.raises((ServiceValidationError, vol.Invalid)):
        await hass.services.async_call(
            "daylight", "from_level", {"daylight_level": True}, blocking=True, return_response=True
        )


async def test_options_preview_does_not_save_until_review(hass, hass_client):
    entry = await setup_entry(hass)
    initial = await hass.config_entries.options.async_init(entry.entry_id)
    assert initial["type"] == "form"
    assert initial["step_id"] == "init"
    review = await hass.config_entries.options.async_configure(
        initial["flow_id"], {"tilt": 90, "facing_mode": "fixed", "bearing": 90}
    )
    assert review["type"] == "menu"
    assert review["step_id"] == "review"
    assert review["menu_options"] == ["save", "init"]
    assert review["description_placeholders"]["preview_url"].startswith("/api/daylight/preview/")
    client = await hass_client()
    response = await client.get(review["description_placeholders"]["preview_url"])
    assert response.status == 200
    assert response.content_type == "image/svg+xml"
    assert "Melanopic EDI" in await response.text()
    assert entry.options == {}
    saved = await hass.config_entries.options.async_configure(
        review["flow_id"], {"next_step_id": "save"}
    )
    assert saved["type"] == "create_entry"
    assert entry.options["tilt"] == 90
    assert entry.options["bearing"] == 90


async def test_orientation_options_refresh_existing_sensors(hass, freezer):
    hass.config.latitude = 40.7
    hass.config.longitude = -74.0
    freezer.move_to("2026-09-26T13:00:00Z")
    entry = await setup_entry(hass)
    before = float(hass.states.get("sensor.daylight_illuminance").state)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    review = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"tilt": 90, "facing_mode": "follow_sun", "bearing": 90}
    )
    await hass.config_entries.options.async_configure(
        review["flow_id"], {"next_step_id": "save"}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data.data["receiver_tilt"] == 90
    assert entry.runtime_data.data["receiver_facing_mode"] == "follow_sun"
    assert float(hass.states.get("sensor.daylight_illuminance").state) != pytest.approx(before)


async def test_review_can_return_to_edit_without_saving(hass):
    entry = await setup_entry(hass)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    review = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"tilt": 45, "facing_mode": "fixed", "bearing": 180}
    )
    edit = await hass.config_entries.options.async_configure(
        review["flow_id"], {"next_step_id": "init"}
    )
    assert edit["step_id"] == "init"
    assert any(key.default() == 45 for key in edit["data_schema"].schema if key.schema == "tilt")
    assert entry.options == {}


async def test_configure_one_device_does_not_change_another(hass):
    first = await setup_entry(hass)
    second = MockConfigEntry(domain="daylight", title="Bedroom", data={})
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    flow = await hass.config_entries.options.async_init(second.entry_id)
    review = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"tilt": 60, "facing_mode": "fixed", "bearing": 90}
    )
    await hass.config_entries.options.async_configure(
        review["flow_id"], {"next_step_id": "save"}
    )
    await hass.async_block_till_done()
    assert first.options == {}
    assert first.runtime_data.data["receiver_tilt"] == 0
    assert second.options["tilt"] == 60
    assert second.runtime_data.data["receiver_tilt"] == 60
