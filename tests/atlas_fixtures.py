import hashlib
import io
import tarfile
from pathlib import Path

import nibabel as nib
import numpy as np

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

[[templates]]
id = "toy-template"
title = "Toy template"
authors = "Test B"
year = 2024
version = "1"
licence = "Toy template licence"
redistribution = true
download = "{download}"
sha256 = "{sha256}"
member = "TOY/template.nii"
volume = "brain"
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


AFFINE = np.array([[4.0, 0, 0, -80.0], [0, 4.0, 0, -96.0], [0, 0, 4.0, -60.0], [0, 0, 0, 1.0]])
SHAPE = (40, 48, 36)
BLOBS = {
    1: ((12, 28, 20), (6, 9, 7)),
    2: ((28, 28, 20), (6, 9, 7)),
    3: ((15, 16, 12), (3, 3, 3)),
    4: ((25, 16, 12), (3, 3, 3)),
    5: ((20, 10, 8), (4, 3, 3)),
}
NAMES = {1: "Alpha_L", 2: "Alpha_R", 3: "Beta_L", 4: "Beta_R", 5: "Gamma"}
TEMPLATE_SHAPE = (20, 24, 18)
TEMPLATE_AFFINE = np.array([[8.0, 0, 0, -80.0], [0, 8.0, 0, -96.0], [0, 0, 8.0, -60.0],
                            [0, 0, 0, 1.0]])


def template_volume(shape=TEMPLATE_SHAPE) -> np.ndarray:
    grid = np.indices(shape).astype(np.float32)
    return 1000.0 + 50.0 * grid[0] + 20.0 * grid[1] + 10.0 * grid[2]


def label_volume(blobs=BLOBS) -> np.ndarray:
    grid = np.indices(SHAPE).transpose(1, 2, 3, 0)
    volume = np.zeros(SHAPE, dtype=np.uint8)
    for value, (center, radii) in blobs.items():
        inside = (((grid - np.array(center)) / np.array(radii)) ** 2).sum(axis=-1) <= 1.0
        volume[inside] = value
    return volume


def make_source_archive(folder: Path, blobs=BLOBS, names=NAMES, template_shape=TEMPLATE_SHAPE,
                        template_affine=TEMPLATE_AFFINE) -> tuple[Path, str]:
    folder.mkdir(parents=True, exist_ok=True)
    image = nib.Nifti1Image(label_volume(blobs), AFFINE)
    template = nib.Nifti1Image(template_volume(template_shape), template_affine)
    table = "".join(f"{value} {name} {value}\n" for value, name in sorted(names.items()))
    archive = folder / "toy_atlas.tar.gz"
    members = (("TOY/toy.nii", image.to_bytes()), ("TOY/toy.txt", table.encode()),
               ("TOY/template.nii", template.to_bytes()))
    with tarfile.open(archive, "w:gz") as tar:
        for name, payload in members:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return archive, hashlib.sha256(archive.read_bytes()).hexdigest()


def build_toy_atlas(root: Path) -> Path:
    from tools.build_atlas.build import build

    archive, sha256 = make_source_archive(root / "upstream")
    src = write_source_tree(root / "src", archive, sha256)
    return build(src, root / "out" / "toy", cache=root / "cache", log=lambda *_: None)
