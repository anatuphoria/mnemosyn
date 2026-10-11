from __future__ import annotations

import nibabel as nib
import numpy as np

AXES = ("axial", "coronal", "sagittal")
AXIS_INDEX = {"sagittal": 0, "coronal": 1, "axial": 2}
DEFAULT_OPACITY = 0.45
OUTLINE = np.array([255.0, 255.0, 255.0], dtype=np.float32)


def slice_count(shape, axis: str) -> int:
    return int(shape[AXIS_INDEX[axis]])


def index_for_mm(affine, shape, axis: str, mm: float) -> int:
    a = AXIS_INDEX[axis]
    index = int(round((mm - affine[a][3]) / affine[a][a]))
    return min(max(index, 0), int(shape[a]) - 1)


def mm_for_index(affine, axis: str, index: int) -> float:
    a = AXIS_INDEX[axis]
    return float(affine[a][3] + affine[a][a] * index)


def is_ras(affine) -> bool:
    return nib.aff2axcodes(np.asarray(affine)) == ("R", "A", "S")


def extract(volume: np.ndarray, affine, axis: str, index: int) -> np.ndarray:
    """Neurological view: patient left on screen left, anterior or superior up."""
    if not is_ras(affine):
        raise ValueError("slices need a volume stored in RAS orientation")
    if axis == "axial":
        return volume[:, :, index].T[::-1, :]
    if axis == "coronal":
        return volume[:, index, :].T[::-1, :]
    return volume[index, :, :].T[::-1, ::-1]


def voxel_for_pixel(shape, axis: str, index: int, row: int, col: int) -> tuple[int, int, int]:
    _, ny, nz = shape[:3]
    if axis == "axial":
        return col, ny - 1 - row, index
    if axis == "coronal":
        return col, index, nz - 1 - row
    return index, ny - 1 - col, nz - 1 - row


def world_for_voxel(affine, voxel) -> tuple[float, float, float]:
    point = np.asarray(affine, dtype=float) @ np.array([*voxel, 1.0])
    return tuple(float(v) for v in point[:3])


def color_table(structures) -> np.ndarray:
    top = max((s.id for s in structures), default=0)
    table = np.zeros((top + 1, 3), dtype=np.uint8)
    for s in structures:
        table[s.id] = s.rgb_triplet
    return table


def mask_table(size: int, ids) -> np.ndarray:
    table = np.zeros(size, dtype=bool)
    table[[i for i in ids if 0 <= i < size]] = True
    return table


def outline(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1)
    inner = padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    return mask & ~inner


def compose(labels, template, colors, hidden, selected, opacity=DEFAULT_OPACITY) -> np.ndarray:
    labels = np.asarray(labels, dtype=np.int64)
    base = (np.zeros(labels.shape, dtype=np.float32) if template is None
            else np.asarray(template, dtype=np.float32))
    rgb = np.repeat(base[..., None], 3, axis=2)
    visible = (labels > 0) & ~hidden[labels]
    chosen = visible & selected[labels]
    alpha = np.where(chosen, 1.0, np.where(visible, opacity, 0.0)).astype(np.float32)[..., None]
    rgb = rgb * (1.0 - alpha) + colors[labels].astype(np.float32) * alpha
    rgb[outline(chosen)] = OUTLINE
    out = np.empty(labels.shape + (4,), dtype=np.uint8)
    out[..., :3] = np.clip(np.rint(rgb), 0, 255)
    out[..., 3] = 255
    return out


def centre_mm(volume, affine, ids) -> tuple[float, float, float] | None:
    mask = np.isin(volume, list(ids))
    if not mask.any():
        return None
    return world_for_voxel(affine, np.argwhere(mask).mean(axis=0))
