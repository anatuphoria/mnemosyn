from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np


class LabelVolume:
    def __init__(self, path: Path, space: str, affine_to_world: np.ndarray) -> None:
        self.path = path
        self.space = space
        self.affine_to_world = np.asarray(affine_to_world, dtype=float)
        self._data: np.ndarray | None = None
        self._world_to_voxel: np.ndarray | None = None

    def _load(self) -> np.ndarray:
        if self._data is None:
            image = nib.load(self.path)
            self._data = np.asanyarray(image.dataobj)
            self._world_to_voxel = np.linalg.inv(self.affine_to_world @ image.affine)
        return self._data

    @property
    def data(self) -> np.ndarray:
        return self._load()

    def label_at(self, point) -> int:
        data = self._load()
        world = np.append(np.asarray(point, dtype=float), 1.0)
        ijk = np.rint(self._world_to_voxel @ world)[:3].astype(int)
        if np.any(ijk < 0) or np.any(ijk >= np.array(data.shape[:3])):
            return 0
        return int(data[tuple(ijk)])
