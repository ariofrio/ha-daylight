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

- `custom_components/daylight/reference.json`: runtime XYZ and melanopic EDI nodes and Planckian locus.
- `docs/reference-provenance.json`: retained/rejected node diagnostics and hashes of source flux files.
- `tools/reference-spectra.csv`: direct-horizontal and diffuse-horizontal spectra for both seeds at every sampled elevation, in W m⁻² nm⁻¹.

To rebuild the small direct-normal lookup for tilted receiving surfaces from that retained CSV:

```sh
uv run --with colour-science==0.4.7 tools/generate_direct_reference.py
```

This writes `custom_components/daylight/direct_reference.json`. It divides direct-horizontal spectra by sin(geometric elevation) at positive elevations, averages both seeds, then reduces XYZ and melanopic EDI. The zero-elevation node is zero by convention. The runtime interpolates this lookup without scientific Python packages.

See [the model documentation](../docs/model.md) for the exact assumptions and limitations. Generated spectra are numerical model outputs, not observations. Paths and location-specific information from the HA installation are not included.

To add or rebuild melanopic EDI from the retained CSV without rerunning libRadtran:

```sh
uv run --with colour-science==0.4.7 tools/melanopic.py
```

`build_reference.py` also invokes this reduction, so full regeneration includes mEDI. The original CIE action-spectrum CSV and metadata are retained under `tools/data/`; their SHA-256 is checked before use. See [data notices](../custom_components/daylight/NOTICE.md). Scientific packages and the action-spectrum CSV are not runtime dependencies.
