import hashlib
import io
import tarfile
import zipfile
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


TOY_PATHWAYS = """\
[[pathways]]
key = "loop"
name = "Toy loop"
start = "alpha gyrus"
group = "Sensory and motor"
steps = [
  { structures = [100] },
  { cross = "Toy crossing" },
  { structures = [150], side = "opposite" },
  { structures = [110], side = "opposite" },
  { relay = "Toy relay", side = "opposite" },
  { structures = [120], side = "midline" },
]

[[pathways]]
key = "short"
name = "Short path"
start = "beta nucleus"
group = "Sensory and motor"
steps = [{ structures = [110] }]
"""

TOY_PATHWAY_TEXTS = {
    "pathway-loop": """\
+++
key = "pathway-loop"
status = "draft"
+++
## Overview
A toy loop that crosses once [ref2020].

## Step 1
Role: Starts in the {same} alpha gyrus [ref2020].
Lesion: Loss on the {opposite} side.

## Step 2
Role: Crosses the midline.
Lesion: Loss on both sides.

## Step 3
Role: Runs down the {opposite} long tract.
Lesion: Loss on the {same} side.

## Step 4
Role: Reaches the {opposite} beta nucleus.
Lesion: Loss on the {same} side.

## Step 5
Role: Relays in a nucleus the atlas lacks.
Lesion: Not described.

## Step 6
Role: Ends in the gamma body.
Lesion: Loss on both sides.
""",
    "pathway-short": """\
+++
key = "pathway-short"
status = "reviewed"
+++
## Overview
One station.

## Step 1
Role: Sits in the {same} beta nucleus.
Lesion: Loss on the {opposite} side [ref2020].
""",
}

TOY_BEHAVIOUR_PATHWAYS = """
[[pathways]]
key = "mood"
name = "Toy mood circuit"
start = "beta nucleus"
group = "Behaviour"
sides = "both"
texts = "behaviour"
steps = [
  { structures = [110] },
  { relay = "Toy relay" },
  { structures = [100] },
  { structures = [120] },
]
"""

TOY_BEHAVIOUR_TEXTS = {"pathway-mood": """\
+++
key = "pathway-mood"
status = "draft"
+++
## Overview
A toy mood loop [ref2020].

## Step 1
Role: Starts in the beta nucleus [ref2020].
Disorders: Toy low mood.
Drugs: Toy pill [ref2020].

## Step 2
Role: Relays.
Disorders: None known.

## Step 3
Role: Reaches the alpha gyrus.
Disorders: Toy worry.

## Step 4
Role: Ends in the gamma body.
Disorders: Toy sleep loss.
Drugs: Toy tea.
"""}

TOY_TIMELINE = """\
route = "mood"
duration = 60
unit = "min"
play_seconds = 6
status = "draft"
note = "Toy curves [ref2020]."

[[curves]]
name = "Toy hormone"
color = [235, 200, 90]
points = [[0, 0.1], [20, 1.0], [60, 0.2]]

[[marks]]
time = 0
step = 1

[[marks]]
time = 20
step = 3

[[marks]]
time = 40
step = 4
"""

TOY_GLAND_PATHWAY = """
[[pathways]]
key = "gland"
name = "Toy gland axis"
start = "beta nucleus"
group = "Behaviour"
sides = "both"
texts = "behaviour"
steps = [{ structures = [110] }, { structures = [170] }]
"""

TOY_GLAND_TEXT = """\
+++
key = "pathway-gland"
status = "draft"
+++
## Overview
A toy gland axis [ref2020].

## Step 1
Role: Starts in the beta nucleus [ref2020].
Disorders: None known.

## Step 2
Role: Releases a toy hormone.
Disorders: Toy gland disease.
"""

TOY_LOCAL_SOURCE = """
[[sources]]
id = "toylocal"
title = "Toy gland"
authors = "Test E"
year = 2024
version = "1"
licence = "No licence stated"
redistribution = false
local_only = true
download = "{download}"
sha256 = "{sha256}"
volume = "brain"
priority = -1
mesh_grid = "native"
mask = true
"""

TOY_LOCAL_STRUCTURES = """\
  { id = 170, parent = 2, acronym = "GLA", name = "Toy gland", source = "toylocal", midline = 1 },
"""

TOY_LOCAL_ENTRY = """\
+++
id = 170
status = "draft"
+++
## Function
Makes toy hormones [ref2020].
"""

TOY_MEMBERS_SOURCE = """
[[sources]]
id = "toymembers"
title = "Toy masks"
authors = "Test F"
year = 2024
version = "1"
licence = "CC0 1.0"
redistribution = true
url = "https://example.org/toy-masks"
{fetch}
sha256 = "{sha256}"
volume = "brain"
priority = -1
mesh_grid = "native"

[sources.members]
Pair_L = "MEM/Pair_L.nii"
Pair_R = "MEM/Pair_R.nii"
Mid = "MEM/Mid.nii"
"""

TOY_MEMBER_STRUCTURES = """\
  { id = 180, parent = 2, acronym = "PR", name = "Toy pair", kind = "nucleus", source = "toymembers", left = "Pair_L", right = "Pair_R" },
  { id = 190, parent = 2, acronym = "MID", name = "Toy middle", kind = "nucleus", source = "toymembers", midline = "Mid" },
"""

MEMBER_SHAPE = (20, 20, 20)
MEMBER_AFFINE = np.array([[2.0, 0, 0, -20.0], [0, 2.0, 0, -60.0], [0, 0, 2.0, 0.0],
                          [0, 0, 0, 1.0]])
MEMBER_BOXES = {"Pair_L": (2, 9), "Pair_R": (12, 19), "Mid": (8, 13)}


def write_member_archive(folder: Path, affines: dict | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / "toy_members.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        for name, (lo, hi) in MEMBER_BOXES.items():
            mask = np.zeros(MEMBER_SHAPE, dtype=np.uint8)
            mask[lo:hi, 5:15, 5:15] = 1
            affine = (affines or {}).get(name, MEMBER_AFFINE)
            zipped.writestr(f"MEM/{name}.nii", nib.Nifti1Image(mask, affine).to_bytes())
    return archive


TOY_SPINE_SOURCES = """
[[volumes]]
name = "spine"
space = "TOYSPINE"
grid_source = "toyspine"

[[sources]]
id = "toyspine"
title = "Toy spinal cord"
authors = "Test G"
year = 2024
version = "1"
licence = "No licence stated"
redistribution = false
local_only = true
download = "{labels}"
sha256 = "{labels_sha}"
volume = "spine"
priority = 0
mesh_grid = "native"
crop = true
margin = 2
fill = true

[[sources]]
id = "toyspine-wm"
title = "Toy spinal tract"
authors = "Test G"
year = 2024
version = "1"
licence = "No licence stated"
redistribution = false
local_only = true
download = "{tract}"
sha256 = "{tract_sha}"
volume = "spine"
priority = 1
mesh_grid = "native"
mask = true

[[templates]]
id = "toyspine-t2"
title = "Toy spinal template"
authors = "Test G"
year = 2024
version = "1"
licence = "No licence stated"
redistribution = false
local_only = true
download = "{template}"
sha256 = "{template_sha}"
volume = "spine"
"""

TOY_CORD_SOURCE = """
[[sources]]
id = "toyspine-cord"
title = "Toy cord outline"
authors = "Test G"
year = 2024
version = "1"
licence = "No licence stated"
redistribution = false
local_only = true
download = "{cord}"
sha256 = "{cord_sha}"
volume = "spine"
priority = 0
mesh_grid = "native"
outline_of = "toyspine"
"""

TOY_SPINE_STRUCTURES = """\
  { id = 200, parent = 2, acronym = "UPS", name = "Upper segment", source = "toyspine", midline = 1 },
  { id = 210, parent = 2, acronym = "LOS", name = "Lower segment", source = "toyspine", midline = 2 },
  { id = 220, parent = 2, acronym = "SPT", name = "Toy spinal tract", kind = "tract", source = "toyspine-wm", midline = 1 },
"""

SPINE_SHAPE = (16, 16, 70)
SPINE_AFFINE = np.array([[-1.0, 0, 0, 8.0], [0, 1.0, 0, -52.0], [0, 0, 1.0, -230.0],
                         [0, 0, 0, 1.0]])


def spine_volume() -> np.ndarray:
    volume = np.zeros(SPINE_SHAPE, dtype=np.uint8)
    volume[6:10, 6:10, 40:60] = 1
    volume[6:10, 6:10, 10:35] = 2
    return volume


LOCAL_SHAPE = (20, 20, 20)
LOCAL_AFFINE = np.array([[-2.0, 0, 0, 20.0], [0, 2.0, 0, 40.0], [0, 0, 2.0, -40.0],
                         [0, 0, 0, 1.0]])


def local_volume() -> np.ndarray:
    grid = np.indices(LOCAL_SHAPE).transpose(1, 2, 3, 0)
    distance = np.linalg.norm(grid - 10, axis=-1)
    return np.where(distance <= 3, 0.9 - 0.1 * distance, 0.0).astype(np.float32)

TOY_BODY_SOURCE = """
[[sources]]
id = "toybody"
title = "Toy body"
authors = "Test H"
year = 2024
version = "1"
licence = "No licence stated"
redistribution = false
local_only = true
download = "{download}"
sha256 = "{sha256}"
volume = "brain"
priority = -5
mesh_grid = "native"
parts = [1, 2]
threshold = 0.5
trim_outside = 6
"""

TOY_BODY_GROUP = """\
  { id = 6, parent = 2, acronym = "STEM", name = "Toy stem" },
"""

TOY_BODY_STRUCTURES = """\
  { id = 230, parent = 6, acronym = "BDA", name = "Toy upper body", kind = "shell", source = "toybody", midline = 1 },
  { id = 240, parent = 6, acronym = "BDB", name = "Toy lower body", kind = "shell", source = "toybody", midline = 2 },
"""

BODY_SHAPE = (29, 43, 97)
BODY_AFFINE = np.array([[2.0, 0, 0, -50.0], [0, 2.0, 0, -50.0], [0, 0, 2.0, -182.0],
                        [0, 0, 0, 1.0]])
BODY_BOXES = {1: ((-50, 0, -20), (-14, 32, 8)), 2: ((-4, -48, -180), (6, -40, -160))}


def body_volume() -> np.ndarray:
    world = np.indices(BODY_SHAPE).transpose(1, 2, 3, 0) * 2.0 + BODY_AFFINE[:3, 3]
    data = np.zeros(BODY_SHAPE + (4,), dtype=np.float32)
    data[..., 0] = 1.0
    for channel, (lo, hi) in BODY_BOXES.items():
        inside = ((world >= lo) & (world <= hi)).all(axis=-1)
        data[inside] = 0.1 * np.eye(4)[0] + 0.9 * np.eye(4)[channel]
        if channel == 1:
            data[inside & (world[..., 2] >= -8) & (world[..., 2] <= -4)] = (0.1, 0.25, 0.05, 0.6)
    return data


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


def write_extended_source_tree(root: Path, tracts: bool, pathways: bool = False,
                               local: bool = False, behaviour: bool = False,
                               members: str = "", spine: bool = False,
                               shells: bool = False, cord: bool = False,
                               lab: bool = False) -> Path:
    archive, sha256 = make_source_archive(root / "upstream")
    src = write_source_tree(root / "src", archive, sha256)
    hyp = root / "upstream" / "toy_hyp.nii.gz"
    nib.save(nib.Nifti1Image(hyp_volume(), HYP_AFFINE), hyp)
    recipe = (src / "recipe.toml").read_text()
    recipe += TOY_HYP_SOURCE.format(download=hyp, sha256=sha256_file(hyp))
    concepts = TOY_HYP_STRUCTURES
    if members:
        archive = write_member_archive(root / "upstream" / "members")
        fetch = ('manual = true\ndownload = "toy_members.zip"' if members == "manual"
                 else f'download = "{archive}"')
        recipe += TOY_MEMBERS_SOURCE.format(fetch=fetch, sha256=sha256_file(archive))
        concepts += TOY_MEMBER_STRUCTURES
    if spine:
        labels = root / "upstream" / "toy_spine.nii.gz"
        nib.save(nib.Nifti1Image(spine_volume(), SPINE_AFFINE), labels)
        template = root / "upstream" / "toy_spine_t2.nii.gz"
        grid = np.indices(SPINE_SHAPE)
        nib.save(nib.Nifti1Image((50 + 10 * grid[0] + grid[2]).astype(np.float32), SPINE_AFFINE),
                 template)
        tract = root / "upstream" / "toy_spine_wm.nii.gz"
        mask = np.zeros(SPINE_SHAPE, dtype=np.uint8)
        mask[6:8, 6:10, 40:60] = 1
        nib.save(nib.Nifti1Image(mask, SPINE_AFFINE), tract)
        recipe += TOY_SPINE_SOURCES.format(labels=labels, labels_sha=sha256_file(labels),
                                           template=template, template_sha=sha256_file(template),
                                           tract=tract, tract_sha=sha256_file(tract))
        concepts += TOY_SPINE_STRUCTURES
        if cord:
            outline = root / "upstream" / "toy_spine_cord.nii.gz"
            mask = np.zeros(SPINE_SHAPE, dtype=np.uint8)
            mask[6:10, 6:10, 4:66] = 1
            nib.save(nib.Nifti1Image(mask, SPINE_AFFINE), outline)
            recipe += TOY_CORD_SOURCE.format(cord=outline, cord_sha=sha256_file(outline))
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
    if local:
        gland = root / "upstream" / "toy_local.nii.gz"
        nib.save(nib.Nifti1Image(local_volume(), LOCAL_AFFINE), gland)
        recipe += TOY_LOCAL_SOURCE.format(download=gland, sha256=sha256_file(gland))
        concepts += TOY_LOCAL_STRUCTURES
        (src / "knowledge" / "en" / "170.md").write_text(TOY_LOCAL_ENTRY)
    groups = ""
    if shells:
        body = root / "upstream" / "toy_body.nii.gz"
        nib.save(nib.Nifti1Image(body_volume(), BODY_AFFINE), body)
        recipe += TOY_BODY_SOURCE.format(download=body, sha256=sha256_file(body))
        concepts += TOY_BODY_STRUCTURES
        groups = TOY_BODY_GROUP
    (src / "recipe.toml").write_text(recipe)
    structures = TOY_STRUCTURES.replace("]\n\nconcepts", groups + "]\n\nconcepts", 1)
    structures = structures.rstrip().removesuffix("]") + concepts + "]\n"
    (src / "structures.toml").write_text(structures)
    if pathways:
        (src / "pathways.toml").write_text(TOY_PATHWAYS)
        for key, text in TOY_PATHWAY_TEXTS.items():
            (src / "knowledge" / "en" / f"{key}.md").write_text(text)
    if behaviour:
        routes = src / "pathways.toml"
        extra = TOY_BEHAVIOUR_PATHWAYS + (TOY_GLAND_PATHWAY if local else "")
        routes.write_text((routes.read_text() if routes.exists() else "") + extra)
        for key, text in TOY_BEHAVIOUR_TEXTS.items():
            (src / "knowledge" / "en" / f"{key}.md").write_text(text)
        if local:
            (src / "knowledge" / "en" / "pathway-gland.md").write_text(TOY_GLAND_TEXT)
        (src / "timelines").mkdir(exist_ok=True)
        (src / "timelines" / "mood.toml").write_text(TOY_TIMELINE)
    if lab:
        (src / "models").mkdir(exist_ok=True)
        (src / "models" / "toy.toml").write_text(TOY_MODEL)
        (src / "knowledge" / "en" / "lab-toy.toml").write_text(TOY_LAB_TEXTS)
    return src


def build_extended_toy_atlas(root: Path, tracts: bool = True, pathways: bool = False,
                             local: bool = False, behaviour: bool = False,
                             lab: bool = False) -> Path:
    from tools.build_atlas.build import build

    src = write_extended_source_tree(root, tracts, pathways, local, behaviour, lab=lab)
    return build(src, root / "out" / "toy", cache=root / "cache", log=lambda *_: None)


TOY_MODEL = """\
key = "toy"
version = 1
route = "mood"
start_clock = "08:00"
settle_speedup = 20
settle_days = 5
max_step = "30 min"
why_threshold = 0.1

[[values]]
key = "x"
unit = "model units"
start = 1.0
display_scale = 10.0
display_unit = "ng/mL"
other_unit = "nmol/L"
other_scale = 2.0
normal = [5, 15]
lane = 1
refs = ["ref2020"]

[[values]]
key = "y"
unit = "model units"
start = 1.0
display_scale = 1.0
display_unit = "times normal"
relative = true
lane = 2

[[values]]
key = "m"
unit = "times normal"
start = 1.0
display_scale = 1.0
display_unit = "times normal"
relative = true
slow = true
lane = 3

[[parameters]]
key = "k"
value = 1.0
unit = "model units"
low = 0.1
high = 10
refs = ["ref2020"]

[[parameters]]
key = "w"
value = 0.1
unit = "/min"
low = 0.01
high = 1
refs = ["ref2020"]

[[parameters]]
key = "a"
value = 0.3
unit = "fraction"
low = 0
high = 0.9

[[parameters]]
key = "stress"
value = 0
unit = "times basal"
low = 0
high = 5

[[parts]]
key = "a"
structure = 111
x = 0
y = 0
values = ["x"]

[[parts]]
key = "b"
structure = 100
x = 1
y = 0
values = ["y"]

[[parts]]
key = "body"
x = 2
y = 0
values = ["m"]

[[effects]]
key = "fb"
expr = "hill(y, k, 2) / hill(1, k, 2)"
kind = "holds back"
arrow = ["b", "a"]

[[effects]]
key = "rhythm"
expr = "1 + a * cos(2 * pi * (clock - 360) / 1440)"
kind = "drives"

[[terms]]
key = "make_x"
value = "x"
sign = 1
expr = "w * fb * rhythm * (1 + stress)"
kind = "drives"
arrow = ["a", "b"]

[[terms]]
key = "clear_x"
value = "x"
sign = -1
expr = "w * x"
kind = "clears"

[[terms]]
key = "make_y"
value = "y"
sign = 1
expr = "w * m * x"
kind = "drives"
arrow = ["b", "body"]

[[terms]]
key = "clear_y"
value = "y"
sign = -1
expr = "w * y"
kind = "clears"

[[terms]]
key = "grow_m"
value = "m"
sign = 1
expr = "0.001 * m * (x - 1)"
kind = "grows"

[[experiments]]
key = "remove_b"
group = "Remove or cut"
mode = "present"
edits = [{ op = "clamp", target = "m", expr = "0" }]

[[experiments]]
key = "pill"
group = "Drugs"
options = [{ key = "dose", unit = "units", default = 1, low = 0, high = 10 }]
edits = [{ op = "dose", target = "y", expr = "dose" }]

[[experiments]]
key = "course"
group = "Drugs"
length = "3 d"
weeks = true
options = [{ key = "dose", unit = "units", default = 1, low = 0, high = 10 }]
edits = [{ op = "dose", target = "y", expr = "dose", daily = true }]

[[experiments]]
key = "stress"
group = "Stressors"
length = "1 h"
options = [{ key = "strength", unit = "times basal", default = 1, low = 0, high = 5 }]
edits = [{ op = "add", target = "stress", expr = "strength" }]

[[tests]]
key = "pill_test"
doses = [{ value = "y", amount = "2" }]
readings = [{ value = "x", after = "1 h" }]
rule = "below"
cutoff = 10.8

[[checks]]
key = "rhythm"
length = "2 d"
asserts = [
  { kind = "peak_within", value = "x", window = ["day 2 00:00", "day 2 23:59"], expect = ["04:00", "10:00"] },
  { kind = "trough_within", value = "x", window = ["day 2 00:00", "day 2 23:59"], expect = ["16:00", "22:00"] },
  { kind = "within", value = "x", at = "day 2 08:00", low = 5, high = 15 },
]

[[checks]]
key = "removal"
length = "1 d"
blocks = [{ experiment = "remove_b", mode = "present" }]
asserts = [{ kind = "vs_normal", value = "x", at = "day 1 12:00", rises = 1.2 }]

[[checks]]
key = "stressed"
length = "1 d"
blocks = [{ experiment = "stress", start = "day 1 10:00" }]
asserts = [
  { kind = "peak_before", first = "x", then = "y", window = ["day 1 10:00", "day 1 14:00"] },
  { kind = "back_to_normal", value = "x", by = "day 1 23:00", tolerance = 0.05 },
]

[[checks]]
key = "tested"
length = "1 d"
blocks = [{ experiment = "pill_test", start = "day 1 10:00" }]
asserts = [{ kind = "test_result", block = 0, expect = "normal" }]

[[normal]]
key = "morning"
from = "04:00"
to = "10:00"

[[normal]]
key = "night"
from = "22:00"
to = "04:00"
"""

TOY_LAB_TEXTS = """\
"name" = "Toy axis"
"scope" = "A toy model with two values and a slow gland [ref2020]."
"normal.morning" = "X rises in the morning [ref2020]."
"normal.night" = "X is low at night."
"value.x.name" = "X"
"value.y.name" = "Y"
"value.y.note" = "Y has no measured unit."
"value.m.name" = "Gland size"
"value.m.note" = "Shown as a multiple of normal."
"parameter.k.name" = "Feedback halfway point"
"parameter.k.meaning" = "Where Y holds back half of X."
"parameter.w.name" = "Clearance"
"parameter.w.meaning" = "How fast both clear."
"parameter.a.name" = "Rhythm depth"
"parameter.a.meaning" = "How deep the daily rhythm is."
"parameter.stress.name" = "Stress"
"parameter.stress.meaning" = "Extra drive from a stressor."
"part.a" = "Alpha"
"part.b" = "Beta"
"part.body" = "Body gland"
"effect.fb" = "Y holds back the making of X [ref2020]."
"effect.rhythm" = "The body clock drives X."
"term.make_x" = "Alpha makes X."
"term.clear_x" = "X is cleared."
"term.make_y" = "The gland makes Y from X."
"term.clear_y" = "Y is cleared."
"term.grow_m" = "X makes the gland grow."
"experiment.remove_b" = "Remove the gland"
"experiment.remove_b.description" = "Takes the gland away."
"experiment.pill" = "Y pill"
"experiment.pill.description" = "A dose of Y."
"experiment.pill.option.dose" = "Dose"
"experiment.course" = "Daily Y course"
"experiment.course.description" = "A dose of Y every day."
"experiment.course.option.dose" = "Dose"
"experiment.stress" = "Short stressor"
"experiment.stress.description" = "An hour of stress."
"experiment.stress.option.strength" = "Strength"
"test.pill_test" = "Y suppression test"
"test.pill_test.description" = "Give Y and read X an hour later."
"test.pill_test.normal" = "X is suppressed, as normal."
"test.pill_test.abnormal" = "X is not suppressed."
"check.rhythm" = "X follows a daily rhythm."
"check.removal" = "Without the gland X rises."
"check.stressed" = "Stress raises X before Y, then both settle."
"check.tested" = "The test is normal in the normal model."
"""
