from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np
from nibabel.processing import resample_from_to

from .hierarchy import PlannedStructure


def read_label_names(path: Path) -> dict[int, str]:
    names = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit():
            names[int(parts[0])] = parts[1]
    return names


def load_label_image(path: Path) -> nib.Nifti1Image:
    image = nib.load(path)
    return nib.Nifti1Image(np.asarray(image.dataobj).astype(np.int32), image.affine)


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
