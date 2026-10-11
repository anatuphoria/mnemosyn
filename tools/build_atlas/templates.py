from __future__ import annotations

import nibabel as nib
import numpy as np
from nibabel.processing import resample_from_to

LOW_PERCENTILE = 0.5
HIGH_PERCENTILE = 99.5


def covers(image: nib.Nifti1Image, shape, affine) -> bool:
    corners = np.array([[i, j, k, 1.0] for i in (0, shape[0] - 1) for j in (0, shape[1] - 1)
                        for k in (0, shape[2] - 1)])
    voxels = (np.linalg.inv(image.affine) @ np.asarray(affine) @ corners.T)[:3]
    limits = np.array(image.shape[:3], dtype=float)[:, None] - 0.5
    return bool(np.all(voxels >= -0.5) and np.all(voxels <= limits))


def on_grid(image: nib.Nifti1Image, shape, affine) -> np.ndarray:
    if image.shape[:3] != tuple(shape) or not np.allclose(image.affine, affine):
        image = resample_from_to(image, (tuple(shape), np.asarray(affine)), order=1)
    return np.asarray(image.dataobj, dtype=np.float32)


def to_uint8(data: np.ndarray) -> np.ndarray:
    low, high = np.percentile(data, [LOW_PERCENTILE, HIGH_PERCENTILE])
    if high <= low:
        return np.zeros(data.shape, dtype=np.uint8)
    scaled = (np.asarray(data, dtype=np.float32) - low) / (high - low) * 255.0
    return np.clip(np.rint(scaled), 0, 255).astype(np.uint8)
