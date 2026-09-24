# Daylight for Home Assistant

A shared, local daylight reference: geometric solar elevation or a normalized daylight level in, illuminance and color temperature out. Install through HACS, confirm setup, and use the resulting sensors and calculation actions in your own automations.

Daylight does not control lights or implement motion handling, dimmer behavior, brightness scaling, or lamp color limits. Those belong in consuming automations.

## Install

Requires Home Assistant 2026.9 or newer.

1. In HACS, add `https://github.com/ariofrio/ha-daylight` as a custom repository of type **Integration**.
2. Download **Daylight**, then restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → Daylight** and confirm.

[Add repository to HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=ariofrio&repository=ha-daylight&category=integration) · [Set up Daylight](https://my.home-assistant.io/redirect/config_flow_start/?domain=daylight)

Manual installation: copy `custom_components/daylight/` into the same location in your HA configuration directory, restart, and complete step 3. HACS is optional. See [HACS integration installation](https://www.hacs.dev/docs/use/repositories/type/integration/).

## Current reference

Setup creates one device with five sensors, updated together every minute using HA's configured latitude, longitude, and time zone:

| Sensor | Value |
|---|---|
| Daylight illuminance | Clear-sky, horizontal solar illuminance in lux |
| Daylight color temperature | CCT in kelvin, or unknown when a useful CCT cannot be reported |
| Daylight level | Normalized elevation from 0 to 1 |
| Daylight geometric solar elevation | Solar-center elevation without refraction, in degrees |
| Daylight noon solar elevation | Today's geometric elevation at solar noon, in degrees |

Entity IDs are assigned by HA and can be renamed. The illuminance sensor also exposes XYZ, xy chromaticity, and Duv attributes. Sensors expose the model identifier, quality, and reason for missing CCT. This is an outdoor solar reference, not measured room brightness.

## Calculation actions

Both actions return a mapping and do not change sensors or lights. Use `response_variable` when calling them from an automation or script. They cannot be called as synchronous Jinja functions; the Python calculation is shared by actions and sensors.

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

Read `daylight_result.lux` and `daylight_result.cct_kelvin` in subsequent templates. CCT may be null: check it before passing a value to a lamp. Actions also return geometry, XYZ, xy, Duv, quality, and model metadata.

`from_level` optionally accepts `noon_elevation` to make the calculation independent of today's location/date. Otherwise it computes today's value from HA's configuration.

The level mapping is:

```text
elevation = -18° + level × (max(-18°, noon_elevation) + 18°)
```

A level of 0 is the dark reference, 1 is today's solar noon, and intermediate values are linear in geometric elevation—not lux or perceived brightness. In polar night when solar noon is below -18°, every level maps to the dark reference. Current level is clamped to [0, 1]. The physical lookup uses a fixed atmosphere and 1 AU solar normalization, so matching morning/evening elevations give matching results.

The actions reject nonfinite or out-of-range inputs. Do not feed HA's ordinary apparent solar elevation directly into this geometric-elevation interface; use this integration's geometric sensor.

## Physical model and limitations

[Model documentation](docs/model.md) describes the fixed atmosphere, spectral calculation, interpolation, numerical checks, and explicitly estimated deep-twilight tail. Version 0.1 is an approximate physical reference, not a calibrated measurement or a forecast of actual conditions.

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

MIT. The initial implementation and documentation were written by Codex at the repository owner's direction; the physical assumptions and limitations are documented for review.
