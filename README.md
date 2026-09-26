# Daylight for Home Assistant

A shared, local daylight reference: geometric solar elevation or a normalized daylight level in, illuminance, melanopic EDI, and color temperature out. Install through HACS, confirm setup, and use the resulting sensors and calculation actions in your own automations.

Daylight does not control lights or implement motion handling, dimmer behavior, brightness scaling, or lamp color limits. Those belong in consuming automations.

## Install

Requires Home Assistant 2026.9 or newer.

1. In HACS, add `https://github.com/ariofrio/ha-daylight` as a custom repository of type **Integration**.
2. Download **Daylight**, then restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → Daylight** and confirm.

[Add repository to HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=ariofrio&repository=ha-daylight&category=integration) · [Set up Daylight](https://my.home-assistant.io/redirect/config_flow_start/?domain=daylight)

Manual installation: copy `custom_components/daylight/` into the same location in your HA configuration directory, restart, and complete step 3. HACS is optional. See [HACS integration installation](https://www.hacs.dev/docs/use/repositories/type/integration/).

## Current reference

Each setup creates one named device with six sensors, updated together every minute using HA's configured latitude, longitude, and time zone. Add Daylight again to create another independently configured receiving surface. The initial receiving surface is horizontal:

| Sensor | Value |
|---|---|
| Daylight illuminance | Clear-sky illuminance on the configured receiving surface, in lux |
| Daylight melanopic EDI | Unscaled, clear-sky melanopic equivalent daylight illuminance on that surface, in lux (CIE S 026 / D65) |
| Daylight color temperature | CCT in kelvin, or unknown when a useful CCT cannot be reported |
| Daylight level | Normalized elevation from 0 to 1 |
| Daylight geometric solar elevation | Solar-center elevation without refraction, in degrees |
| Daylight noon solar elevation | Today's geometric elevation at solar noon, in degrees |

Entity IDs are assigned by HA and can be renamed. The illuminance sensor also exposes XYZ, xy chromaticity, and Duv attributes. Sensors expose the model identifier, quality, and reason for missing CCT. The melanopic EDI sensor exposes `melanopic_edi_reason` and `relative_melanopic_spread` (a paired-simulation diagnostic, not an accuracy bound). Its unit is lx, but it is a distinct spectral metric from ordinary illuminance. No indoor multiplier, lamp calibration, or scheduling is applied. This is an outdoor solar reference, not measured room brightness.

## Configure the receiving surface

Open **Settings → Devices & services → Daylight → Configure** for the device you want to adjust. One form contains tilt (0° horizontal to 90° vertical), facing mode (fixed bearing or follow the sun), and compass bearing (0° north, 90° east, 180° south, 270° west). Bearing is ignored in follow-sun mode. Continue to see a static full-day preview of illuminance, melanopic EDI, and CCT for the unsaved settings. Choose **Save settings** to apply the values or **Back to settings** to revise them. Saving updates that device's existing sensor entities without resetting their history.

All tilts use one receiving-plane calculation: direct sunlight follows its incidence angle, and diffuse sky plus ground light comes from the fixed-atmosphere directional spectral reference. The horizontal result is its 0° case. Values between simulated directions are interpolated and remain clear-sky **estimates**; the preview and live sensors use the same model. The sensors expose `receiver_tilt`, `receiver_facing_mode`, `receiver_bearing`, and `orientation_model` attributes so a change in their history can be interpreted. The [model documentation](docs/model.md#tilted-receiving-surfaces) details the calculation and limits.

The Configure dialog has a generated image, so it updates after continuing to the review step, not while dragging a slider. Its signed image URL expires after 15 minutes; return to the first step and preview again if needed.

## Calculation actions

Both actions return the original **horizontal** reference, regardless of the device's configured orientation, and do not change sensors or lights. Use `response_variable` when calling them from an automation or script. They cannot be called as synchronous Jinja functions.

```yaml
- action: daylight.from_elevation
  data:
    geometric_elevation: 20
  response_variable: daylight_result
```

```yaml
- action: daylight.from_level
  data:
    daylight_level: 0.35
  response_variable: daylight_result
```

Read `daylight_result.lux`, `daylight_result.melanopic_edi`, and `daylight_result.cct_kelvin` in subsequent templates. CCT may be null: check it before passing a value to a lamp. Melanopic EDI is independent of CCT and may remain available when CCT is null. Between -18° and -10°, melanopic EDI is null with `melanopic_edi_reason: outside_numerically_resolved_table`; at or below -18° it is zero with `no_solar_reference`. Actions also return geometry, XYZ, xy, Duv, quality, and model metadata.

`from_level` optionally accepts `noon_elevation` to make the calculation independent of today's location/date. Otherwise it computes today's value from HA's configuration.

The level mapping is:

```text
elevation = -18° + level × (max(-18°, noon_elevation) + 18°)
```

A level of 0 is the dark reference, 1 is today's solar noon, and intermediate values are linear in geometric elevation—not lux or perceived brightness. In polar night when solar noon is below -18°, every level maps to the dark reference. Current level is clamped to [0, 1]. The physical lookup uses a fixed atmosphere and 1 AU solar normalization, so matching morning/evening elevations give matching results.

The actions reject nonfinite or out-of-range inputs.

**Geometric elevation** is the sun's position without atmospheric refraction; **apparent elevation** includes the bending of sunlight through the atmosphere. Daylight uses geometric elevation, while HA's built-in `sun.sun` reports apparent elevation. Use Daylight's geometric sensor with `from_elevation`: passing apparent elevation won't fail validation, but gives results for a shifted sun position, especially near the horizon.

## Physical model and limitations

[Model documentation](docs/model.md) describes the fixed atmosphere, spectral calculation, interpolation, numerical checks, and explicitly estimated deep-twilight tail. This is an approximate physical reference, not a calibrated measurement or a forecast of actual conditions.

The reference includes daylight and twilight. It does not assume dimmer light is always warmer: diffuse twilight can be very blue. It does not clamp scientific CCT to a lamp's supported range.

## Development

```sh
uv venv --python 3.14
uv pip install -r requirements-test.txt
uv run --no-project pytest
uv run --no-project ruff check .
```

See [reference generation](tools/README.md) for the offline scientific workflow. No scientific solver, cloud service, API credential, or large numerical dependency runs inside HA.

## Removal

Delete the Daylight integration under Devices & services, then remove its download from HACS and restart HA. Remove or update automations referencing its actions/sensors first.

## License and authorship

Code is MIT. The CIE action-spectrum data and derived melanopic reference values carry CC BY-SA 4.0 attribution; see [data notices](custom_components/daylight/NOTICE.md). The initial implementation and documentation were written by Codex at the repository owner's direction; the physical assumptions and limitations are documented for review.
