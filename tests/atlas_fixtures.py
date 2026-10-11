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


HYP_SHAPE = (80, 96, 72)
HYP_AFFINE = np.array([[2.0, 0, 0, -80.0], [0, 2.0, 0, -96.0], [0, 0, 2.0, -60.0],
                       [0, 0, 0, 1.0]])
HYP_BLOBS = {1: ((24, 74, 40), (4, 4, 4)), 2: ((56, 74, 40), (4, 4, 4)),
             4: ((40, 20, 20), (3, 3, 3))}
TINY_VOXEL = (41, 41, 41)
TRACT_SHAPE = (30, 36, 28)
TRACT_AFFINE = np.array([[4.0, 0, 0, -72.0], [0, 4.0, 0, -88.0], [0, 0, 4.0, -52.0],
                         [0, 0, 0, 1.0]])
TRACT_BOXES = {
    "Long_Tract_L": ((6, 10, 2), (10, 14, 26)),
    "Long_Tract_R": ((20, 10, 2), (24, 14, 26)),
    "Short_Tract": ((6, 11, 12), (24, 13, 14)),
    "Extra": ((14, 30, 5), (15, 31, 6)),
}

TOY_HYP_SOURCE = """
[[sources]]
id = "toyhyp"
title = "Toy hypothalamus"
authors = "Test C"
year = 2024
version = "1"
licence = "CC BY 4.0"
redistribution = true
download = "{download}"
sha256 = "{sha256}"
volume = "brain"
priority = 0
drop = [4]
mesh_grid = "native"
"""

TOY_TRACT_SOURCE = """
[[tracts]]
id = "toytracts"
title = "Toy tracts"
authors = "Test D"
year = 2024
version = "1"
licence = "CC BY-SA 4.0"
redistribution = true
download = "{download}"
labels = "brain"
drop = ["Extra"]

[tracts.files]
{files}
"""

TOY_HYP_STRUCTURES = """\
  { id = 130, parent = 2, acronym = "DEL", name = "Delta nucleus", kind = "nucleus", source = "toyhyp", left = 1, right = 2 },
  { id = 140, parent = 2, acronym = "TIN", name = "Tiny nucleus", kind = "nucleus", source = "toyhyp", midline = 3 },
"""

TOY_TRACT_STRUCTURES = """\
  { id = 150, parent = 2, acronym = "LT", name = "Long tract", kind = "tract", source = "toytracts", left = "Long_Tract_L", right = "Long_Tract_R" },
  { id = 160, parent = 2, acronym = "ST", name = "Short tract", kind = "tract", source = "toytracts", midline = "Short_Tract" },
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hyp_volume() -> np.ndarray:
    grid = np.indices(HYP_SHAPE).transpose(1, 2, 3, 0)
    volume = np.zeros(HYP_SHAPE, dtype=np.uint8)
    for value, (center, radii) in HYP_BLOBS.items():
        inside = (((grid - np.array(center)) / np.array(radii)) ** 2).sum(axis=-1) <= 1.0
        volume[inside] = value
    volume[TINY_VOXEL] = 3
    return volume


def write_extended_source_tree(root: Path, tracts: bool) -> Path:
    archive, sha256 = make_source_archive(root / "upstream")
    src = write_source_tree(root / "src", archive, sha256)
    hyp = root / "upstream" / "toy_hyp.nii.gz"
    nib.save(nib.Nifti1Image(hyp_volume(), HYP_AFFINE), hyp)
    recipe = (src / "recipe.toml").read_text()
    recipe += TOY_HYP_SOURCE.format(download=hyp, sha256=sha256_file(hyp))
    concepts = TOY_HYP_STRUCTURES
    if tracts:
        folder = root / "upstream" / "tracts"
        folder.mkdir()
        lines = []
        for name, (lo, hi) in sorted(TRACT_BOXES.items()):
            mask = np.zeros(TRACT_SHAPE, dtype=np.uint8)
            mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] = 1
            path = folder / f"{name}.nii.gz"
            nib.save(nib.Nifti1Image(mask, TRACT_AFFINE), path)
            lines.append(f'{name} = "{sha256_file(path)}"')
        recipe += TOY_TRACT_SOURCE.format(download=folder / "{name}.nii.gz",
                                          files="\n".join(lines))
        concepts += TOY_TRACT_STRUCTURES
    (src / "recipe.toml").write_text(recipe)
    structures = TOY_STRUCTURES.rstrip().removesuffix("]") + concepts + "]\n"
    (src / "structures.toml").write_text(structures)
    return src


def build_extended_toy_atlas(root: Path, tracts: bool = True) -> Path:
    from tools.build_atlas.build import build

    src = write_extended_source_tree(root, tracts)
    return build(src, root / "out" / "toy", cache=root / "cache", log=lambda *_: None)
