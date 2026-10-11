from __future__ import annotations

from cns_atlas import Atlas

DEFAULT_FACE_BUDGET = 3_000_000
LEVELS = (0, 1, 2)


def choose_lod(face_totals: list[int], budget: int = DEFAULT_FACE_BUDGET) -> int:
    for level, total in enumerate(face_totals):
        if total <= budget:
            return level
    return len(face_totals) - 1


def face_totals(atlas: Atlas, ids) -> list[int]:
    totals = []
    for level in LEVELS:
        meshes = (atlas.mesh(structure_id, level) for structure_id in ids)
        totals.append(sum(len(mesh.faces) for mesh in meshes if mesh is not None))
    return totals
