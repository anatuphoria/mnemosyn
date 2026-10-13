from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np
from nibabel.processing import resample_from_to

from .fetch import member_path
from .hierarchy import PlannedStructure
from .recipe import BuildError, SourceSpec


def read_label_names(path: Path) -> dict[int, str]:
    names = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit():
            names[int(parts[0])] = parts[1]
    return names


CROP_SLAB = 32


def _box(proxy) -> tuple[np.ndarray, np.ndarray] | None:
    lo = hi = None
    for z in range(0, proxy.shape[2], CROP_SLAB):
        index = np.argwhere(np.nan_to_num(np.asarray(proxy[:, :, z:z + CROP_SLAB])) != 0)
        if len(index):
            index[:, 2] += z
            lo = index.min(axis=0) if lo is None else np.minimum(lo, index.min(axis=0))
            hi = index.max(axis=0) if hi is None else np.maximum(hi, index.max(axis=0))
    return None if lo is None else (lo, hi)


def load_label_image(path: Path, mask: bool = False, name: str = "", cropped: bool = False,
                     threshold: float | None = None, margin: float = 0.0) -> nib.Nifti1Image:
    image = nib.load(path, keep_file_open=True) if cropped else nib.load(path)
    affine = image.affine
    if cropped:
        box = _box(image.dataobj)
        if box is None:
            raise BuildError([f"source {name}: has no labels"])
        pad = np.ceil(margin / np.asarray(image.header.get_zooms()[:3], dtype=float)).astype(int)
        lo = np.maximum(box[0] - 1 - pad, 0)
        hi = np.minimum(box[1] + 2 + pad, image.shape[:3])
        data = np.asarray(image.dataobj[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]])
        shift = np.eye(4)
        shift[:3, 3] = lo
        affine = np.asarray(affine) @ shift
    else:
        data = np.asarray(image.dataobj)
    if mask:
        data = np.nan_to_num(data)
        data = data >= threshold if threshold is not None else data != 0
    elif not np.issubdtype(data.dtype, np.integer) and np.any(data != np.rint(data)):
        raise BuildError([f"source {name}: label values are not whole numbers; set mask = true"])
    return nib.Nifti1Image(data.astype(np.int32), affine)


def member_masks(spec: SourceSpec, archive: Path):
    shape, affine = None, None
    for value, (name, member) in enumerate(spec.members, 1):
        image = nib.load(member_path(spec, archive, member))
        if shape is None:
            shape, affine = image.shape[:3], image.affine
        elif image.shape[:3] != shape or not np.allclose(image.affine, affine):
            raise BuildError([f"source {spec.source.id}: member {name} is on another grid"])
        values = np.nan_to_num(np.asarray(image.dataobj)).reshape(shape)
        inside = values >= spec.threshold if spec.threshold is not None else values != 0
        yield value, inside, affine


def separate_natives(spec: SourceSpec, archive: Path, mapping: dict[int, int]
                     ) -> list[tuple[np.ndarray, np.ndarray]]:
    natives = []
    for value, inside, affine in member_masks(spec, archive):
        if value in mapping:
            data, cropped_affine = crop(inside, affine)
            natives.append((data.astype(np.uint16) * mapping[value], cropped_affine))
    return natives


def load_members(spec: SourceSpec, archive: Path) -> tuple[nib.Nifti1Image, int]:
    out, affine, lost = None, None, 0
    for value, inside, affine in member_masks(spec, archive):
        if out is None:
            out = np.zeros(inside.shape, dtype=np.int32)
        lost += int((inside & (out != 0)).sum())
        out[inside & (out == 0)] = value
    return nib.Nifti1Image(out, affine), lost


def source_values(image: nib.Nifti1Image) -> set[int]:
    return set(np.unique(np.asarray(image.dataobj)).tolist()) - {0}


def mapping_for(source_id: str, planned: list[PlannedStructure]) -> dict[int, int]:
    return {ref.value: p.structure.id for p in planned for ref in p.labels
            if ref.source == source_id}


def relabel(image: nib.Nifti1Image, mapping: dict) -> np.ndarray:
    values = np.asarray(image.dataobj)
    if not np.issubdtype(values.dtype, np.integer):
        values = np.rint(values)
    values = np.clip(values, 0, None).astype(np.int32, copy=False)
    lookup = np.zeros(int(values.max(initial=0)) + 1, dtype=np.uint16)
    for value, structure_id in mapping.items():
        if isinstance(value, int) and 0 <= value < len(lookup):
            lookup[value] = structure_id
    return lookup[values]


def crop(data: np.ndarray, affine: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    index = np.argwhere(data > 0)
    if not len(index):
        return data, affine
    lo, hi = index.min(axis=0), index.max(axis=0) + 1
    shift = np.eye(4)
    shift[:3, 3] = lo
    return data[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]], np.asarray(affine) @ shift


def merge(grid: nib.Nifti1Image, layers: list[tuple[int, nib.Nifti1Image, dict[int, int]]]
          ) -> np.ndarray:
    out = np.zeros(grid.shape[:3], dtype=np.uint16)
    for _, image, mapping in sorted(layers, key=lambda layer: layer[0]):
        if image.shape[:3] != grid.shape[:3] or not np.allclose(image.affine, grid.affine):
            image = resample_from_to(image, (grid.shape[:3], grid.affine), order=0)
        mapped = relabel(image, mapping)
        out[mapped > 0] = mapped[mapped > 0]
    return out
