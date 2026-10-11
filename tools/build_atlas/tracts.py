from __future__ import annotations

import nibabel as nib
import numpy as np

from .recipe import BuildError


def place(image: nib.Nifti1Image, shape, affine, label: str) -> np.ndarray:
    offset = np.linalg.inv(np.asarray(affine, dtype=float)) @ np.asarray(image.affine, dtype=float)
    shift = np.rint(offset[:3, 3])
    if not np.allclose(offset[:3, :3], np.eye(3)) or not np.allclose(offset[:3, 3], shift):
        raise BuildError([f"{label}: grid is not a whole-voxel offset of the label grid"])
    ijk = np.argwhere(np.asarray(image.dataobj) > 0) + shift.astype(np.int64)
    inside = np.all((ijk >= 0) & (ijk < np.asarray(shape[:3])), axis=1)
    if not inside.all():
        raise BuildError([f"{label}: {int((~inside).sum())} voxels fall outside the label grid"])
    return np.unique(np.ravel_multi_index(ijk.T, tuple(shape[:3]))).astype(np.uint32)
