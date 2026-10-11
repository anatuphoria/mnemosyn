from pathlib import Path

TOY_RECIPE = """\
name = "toy-atlas"
version = "0.0.1"
species = "Homo sapiens"
licence = "CC BY 4.0"
lod0_max_faces = 2000
lod_fractions = [1.0, 0.25, 0.05]
min_faces = 64
smoothing_iterations = 20
smoothing_pass_band = 0.1

[[volumes]]
name = "brain"
space = "MNI152"
grid_source = "toy"

[[sources]]
id = "toy"
title = "Toy labelled atlas"
authors = "Test A"
year = 2024
version = "1"
licence = "CC0 1.0"
redistribution = true
download = "{download}"
sha256 = "{sha256}"
member = "TOY/toy.nii"
label_names = "TOY/toy.txt"
volume = "brain"
priority = 1
"""

TOY_STRUCTURES = """\
default_source = "toy"

groups = [
  { id = 1, acronym = "CNS", name = "Central nervous system" },
  { id = 2, parent = 1, acronym = "Br", name = "Brain", color = [120, 140, 200] },
]

concepts = [
  { id = 100, parent = 2, acronym = "ALG", name = "Alpha gyrus", left = 1, right = 2, synonyms = ["first gyrus"] },
  { id = 110, parent = 2, acronym = "BEN", name = "Beta nucleus", kind = "nucleus", left = 3, right = 4, color = [230, 120, 120] },
  { id = 120, parent = 2, acronym = "GAM", name = "Gamma body", kind = "nucleus", midline = 5 },
]
"""

TOY_REFERENCES = """\
[ref2020]
authors = "Author A"
title = "A reference"
year = 2020
url = "https://example.org/ref"
"""

TOY_ENTRY = """\
+++
id = 100
status = "draft"
+++
## Function
Does alpha things [ref2020].
"""


def write_source_tree(root: Path, download, sha256: str) -> Path:
    (root / "knowledge" / "en").mkdir(parents=True, exist_ok=True)
    (root / "recipe.toml").write_text(TOY_RECIPE.format(download=download, sha256=sha256))
    (root / "structures.toml").write_text(TOY_STRUCTURES)
    (root / "knowledge" / "references.toml").write_text(TOY_REFERENCES)
    (root / "knowledge" / "en" / "100.md").write_text(TOY_ENTRY)
    return root
