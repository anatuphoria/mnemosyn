
```bash
python -m venv .venv
.venv/bin/pip install -e ".[desktop,atlas-build,dev]"
.venv/bin/python -m tools.build_atlas    # downloads the open atlases and builds atlases/cns
.venv/bin/python -m tools.build_atlas --local    # also adds sources not yet allowed to be shared
.venv/bin/mnemosyn                       # desktop app
```

A rebuild compares itself with the atlas it replaces: its build report lists structures removed,
renamed or moved, and a removal or rename stops the build unless you add `--accept-changes`.

On hybrid-GPU laptops, `prime-run .venv/bin/mnemosyn` uses the discrete GPU.

