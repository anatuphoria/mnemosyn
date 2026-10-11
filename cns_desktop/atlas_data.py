from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pyvista as pv

from brain_tui.atlas import load_regions

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class Structure:
    id: str
    name: str
    system: str
    color: tuple[int, int, int]
    mesh: pv.PolyData


@dataclass(frozen=True)
class Atlas:
    name: str
    structures: dict[str, Structure]

    def by_system(self) -> dict[str, list[Structure]]:
        groups: dict[str, list[Structure]] = {}
        for s in self.structures.values():
            groups.setdefault(s.system, []).append(s)
        return {k: sorted(v, key=lambda s: s.name) for k, v in sorted(groups.items())}


def default_manifest() -> str | None:
    for candidate in ("data/manifest_aal.json", "data/manifest.json"):
        path = os.path.join(REPO_ROOT, candidate)
        if os.path.exists(path):
            return path
    return None


def load_atlas(manifest: str | None = None) -> Atlas:
    manifest = manifest or default_manifest()
    structures = {}
    for r in load_regions(manifest).values():
        verts = r.mesh.verts - r.mesh.centroid + r.base_center
        mesh = pv.PolyData.from_regular_faces(np.asarray(verts, dtype=np.float32), r.mesh.faces)
        mesh = mesh.compute_normals(cell_normals=False, split_vertices=False)
        structures[r.id] = Structure(r.id, r.name, r.system, tuple(r.color), mesh)
    name = os.path.basename(manifest) if manifest else "procedural"
    return Atlas(name=name, structures=structures)
