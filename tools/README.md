# Reproducing the reference

Build [libRadtran 2.0.6](https://www.libradtran.org/doku.php?id=download) with MYSTIC support and its scientific dependencies. The build is separate from the HA installation; the runtime does not need it.

Generate all release nodes and aggregate them:

```sh
uv run --with colour-science==0.4.7 tools/generate_reference.py \
  --libradtran /path/to/libRadtran-2.0.6 \
  --work ./work/reference-runs --workers 4
```

This is a substantial offline calculation. The directory contains per-run inputs, spectral fluxes, seeds, and timing. Completed runs are reused. Delete a failed run's directory before retrying.

To rebuild only the derived artifact from completed runs:

```sh
uv run --with colour-science==0.4.7 tools/build_reference.py ./work/reference-runs
```

Outputs:

- `custom_components/daylight/reference.json`: runtime XYZ nodes and Planckian locus.
- `docs/reference-provenance.json`: retained/rejected node diagnostics and hashes of source flux files.
- `tools/reference-spectra.csv`: direct-horizontal and diffuse-horizontal spectra for both seeds at every sampled elevation, in W m⁻² nm⁻¹.

See [the model documentation](../docs/model.md) for the exact assumptions and limitations. Generated spectra are numerical model outputs, not observations. Paths and location-specific information from the HA installation are not included.
