# Fixed-atmosphere daylight reference

The runtime interpolates a versioned table generated using [libRadtran 2.0.6](https://www.libradtran.org/doku.php?id=download), with the fully spherical MYSTIC solver and independent wavelength calculations. The table covers a horizontal, unobstructed receiver at sea level. It is a reference atmosphere, not a reconstruction of actual local weather.

## Inputs

- US-standard vertical atmosphere; Earth radius 6370 km.
- Default aerosol profile, aerosol optical depth at 500 nm = 0.1, Ångström exponent 1.14.
- Ozone column 300 DU; Lambertian ground albedo 0.2; no clouds.
- Shipped Kurucz solar spectrum, fixed 1 AU normalization.
- 360–830 nm at 1 nm spacing; REPTRAN coarse gas absorption; unpolarized light; no refraction.

The 1 nm output grid does not remove the gas-absorption parameterization's band approximation. Morning and evening use identical atmospheric inputs. HA's configured altitude does not change the table's sea-level atmosphere.

## Lux and color

The generator combines diffuse horizontal spectral irradiance with the direct solar component projected onto the horizontal plane. In this specific nonrefracting spherical backward setup, MYSTIC's `edir` output requires the sine-of-elevation projection before addition. This was checked against the package's deterministic direct-beam calculation during model research. See [solver source](https://www.libradtran.org/download/libRadtran-2.0.6.tar.gz), `libsrc_c/mystic.c`, `direct_radiation()`.

The combined spectrum is integrated using CIE 1931 2° color-matching functions. Photopic lux is 683 × Y. CCT is derived from the combined XYZ, not an average of component Kelvin values. Source spectra are retained in [reference-spectra.csv](../tools/reference-spectra.csv); provenance and paired-run differences are in [reference-provenance.json](reference-provenance.json).

The runtime uses [shape-preserving cubic (PCHIP) interpolation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.PchipInterpolator.html) of log XYZ between elevation nodes. Its CCT routine projects CIE 1960 uv onto a densely sampled Planckian locus and interpolates inverse temperature. Tests compare that calculation with colour-science's Ohno 2013 implementation.

[Independent simulations at six withheld elevations](interpolation-check.json) differed from the interpolated illuminance by 0.06–0.26% at the five daytime samples (0.5°, 4°, 25°, 52.5°, 82.5°), and 2.99% at -3°. Maximum CIE 1960 uv distance was 0.000953. These comparisons include Monte Carlo sampling noise; they are numerical consistency checks, not validation against measured skies or error bounds at every elevation.

CCT is omitted outside the 1500–25000 K reporting range, beyond |Duv| = 0.02, or where paired-run uv disagreement exceeds 0.005. These are engineering reporting limits, not physical limits on possible daylight colors. XYZ/xy remain available for modeled light even when CCT is omitted.

## Twilight and numerical quality

Each diffuse node has two independent seeds. The generator retains a contiguous suffix of nodes with positive estimates and paired lux disagreement no greater than 25%, starting no later than -6°. Paired disagreement is a diagnostic; two seeds do not establish total uncertainty or accuracy. `reference` means the bounding nodes' paired lux disagreement is at most 2% and uv disagreement at most 0.001; `approximate` means those stricter thresholds are exceeded. Neither label establishes measurement accuracy or excludes interpolation/systematic error.

The released table starts at -10°. Below it, `estimated_twilight` uses an exponential continuation of the first interval's Y slope, tapered to zero at -18°. This is an explicit engineering approximation, not a converged radiative-transfer prediction. It reports no CCT or chromaticity. At or below -18°, the solar reference is zero and CCT is absent. This convention does not assert that physical solar scattering is exactly zero; moonlight, airglow, starlight, artificial light, and atmospheric variability are also excluded.

The model is approximate near the horizon: finite solar-disc and refraction effects are not modeled. Broad-band ALIS spectral acceleration was deliberately excluded after earlier tests found inconsistent twilight color. [MYSTIC geometry and benchmark documentation](https://www.libradtran.org/doku.php?id=basic_usage).

## Solar geometry and level

Astral, as supplied by HA, computes geometric elevation with `with_refraction=False`. Solar noon uses HA's configured local date. The normalized level spans -18° to that day's solar-noon elevation. It is not a perceptual dimming curve. Brightness scaling, color gamut mapping, minimum light levels, and motion/rotary input behavior belong to another abstraction.
