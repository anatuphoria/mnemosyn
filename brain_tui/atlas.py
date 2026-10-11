from __future__ import annotations

import json
import os
import numpy as np

from .scene import Mesh, Region

AAL_116 = [
    "Precentral_L", "Precentral_R", "Frontal_Sup_L", "Frontal_Sup_R",
    "Frontal_Sup_Orb_L", "Frontal_Sup_Orb_R", "Frontal_Mid_L", "Frontal_Mid_R",
    "Frontal_Mid_Orb_L", "Frontal_Mid_Orb_R", "Frontal_Inf_Oper_L", "Frontal_Inf_Oper_R",
    "Frontal_Inf_Tri_L", "Frontal_Inf_Tri_R", "Frontal_Inf_Orb_L", "Frontal_Inf_Orb_R",
    "Rolandic_Oper_L", "Rolandic_Oper_R", "Supp_Motor_Area_L", "Supp_Motor_Area_R",
    "Olfactory_L", "Olfactory_R", "Frontal_Sup_Medial_L", "Frontal_Sup_Medial_R",
    "Frontal_Med_Orb_L", "Frontal_Med_Orb_R", "Rectus_L", "Rectus_R",
    "Insula_L", "Insula_R", "Cingulum_Ant_L", "Cingulum_Ant_R",
    "Cingulum_Mid_L", "Cingulum_Mid_R", "Cingulum_Post_L", "Cingulum_Post_R",
    "Hippocampus_L", "Hippocampus_R", "ParaHippocampal_L", "ParaHippocampal_R",
    "Amygdala_L", "Amygdala_R", "Calcarine_L", "Calcarine_R",
    "Cuneus_L", "Cuneus_R", "Lingual_L", "Lingual_R",
    "Occipital_Sup_L", "Occipital_Sup_R", "Occipital_Mid_L", "Occipital_Mid_R",
    "Occipital_Inf_L", "Occipital_Inf_R", "Fusiform_L", "Fusiform_R",
    "Postcentral_L", "Postcentral_R", "Parietal_Sup_L", "Parietal_Sup_R",
    "Parietal_Inf_L", "Parietal_Inf_R", "SupraMarginal_L", "SupraMarginal_R",
    "Angular_L", "Angular_R", "Precuneus_L", "Precuneus_R",
    "Paracentral_Lobule_L", "Paracentral_Lobule_R", "Caudate_L", "Caudate_R",
    "Putamen_L", "Putamen_R", "Pallidum_L", "Pallidum_R",
    "Thalamus_L", "Thalamus_R", "Heschl_L", "Heschl_R",
    "Temporal_Sup_L", "Temporal_Sup_R", "Temporal_Pole_Sup_L", "Temporal_Pole_Sup_R",
    "Temporal_Mid_L", "Temporal_Mid_R", "Temporal_Pole_Mid_L", "Temporal_Pole_Mid_R",
    "Temporal_Inf_L", "Temporal_Inf_R", "Cerebellum_Crus1_L", "Cerebellum_Crus1_R",
    "Cerebellum_Crus2_L", "Cerebellum_Crus2_R", "Cerebellum_3_L", "Cerebellum_3_R",
    "Cerebellum_45_L", "Cerebellum_45_R", "Cerebellum_6_L", "Cerebellum_6_R",
    "Cerebellum_7b_L", "Cerebellum_7b_R", "Cerebellum_8_L", "Cerebellum_8_R",
    "Cerebellum_9_L", "Cerebellum_9_R", "Cerebellum_10_L", "Cerebellum_10_R",
    "Vermis_123", "Vermis_456", "Vermis_7", "Vermis_8", "Vermis_910",
    "Brainstem_Midbrain", "Brainstem_Pons", "Brainstem_Medulla",
]


def make_ellipsoid(rx: float, ry: float, rz: float, n_lat: int = 8, n_lon: int = 12) -> Mesh:
    verts: list[list[float]] = []
    for i in range(n_lat + 1):
        theta = np.pi * i / n_lat
        for j in range(n_lon):
            phi = 2 * np.pi * j / n_lon
            x = rx * np.sin(theta) * np.cos(phi)
            y = ry * np.cos(theta)
            z = rz * np.sin(theta) * np.sin(phi)
            verts.append([x, y, z])
    verts = np.array(verts, dtype=np.float32)
    faces: list[list[int]] = []
    for i in range(n_lat):
        for j in range(n_lon):
            a = i * n_lon + j
            b = i * n_lon + (j + 1) % n_lon
            c = (i + 1) * n_lon + j
            d = (i + 1) * n_lon + (j + 1) % n_lon
            if i > 0:
                faces.append([a, c, b])
            if i < n_lat - 1:
                faces.append([b, c, d])
    return Mesh(verts=verts, faces=np.array(faces, dtype=np.int32))


def _procedural_defs() -> list[tuple]:
    F = (86, 140, 230)
    P = (86, 200, 170)
    T = (230, 170, 80)
    O = (200, 110, 220)
    S = (235, 120, 120)
    C = (140, 180, 120)
    B = (180, 170, 160)
    defs = [
        ("frontal_sup_L", "Frontal_Sup_L", "frontal", F, (-0.42, 0.45, 0.55), (0.34, 0.38, 0.42)),
        ("frontal_sup_R", "Frontal_Sup_R", "frontal", F, (0.42, 0.45, 0.55), (0.34, 0.38, 0.42)),
        ("frontal_mid_L", "Frontal_Mid_L", "frontal", F, (-0.55, 0.10, 0.55), (0.28, 0.34, 0.40)),
        ("frontal_mid_R", "Frontal_Mid_R", "frontal", F, (0.55, 0.10, 0.55), (0.28, 0.34, 0.40)),
        ("frontal_inf_L", "Frontal_Inf_Tri_L", "frontal", F, (-0.50, -0.20, 0.45), (0.24, 0.26, 0.32)),
        ("frontal_inf_R", "Frontal_Inf_Tri_R", "frontal", F, (0.50, -0.20, 0.45), (0.24, 0.26, 0.32)),
        ("precentral_L", "Precentral_L", "frontal", F, (-0.58, 0.15, 0.05), (0.20, 0.45, 0.28)),
        ("precentral_R", "Precentral_R", "frontal", F, (0.58, 0.15, 0.05), (0.20, 0.45, 0.28)),
        ("postcentral_L", "Postcentral_L", "parietal", P, (-0.60, 0.15, -0.30), (0.20, 0.44, 0.26)),
        ("postcentral_R", "Postcentral_R", "parietal", P, (0.60, 0.15, -0.30), (0.20, 0.44, 0.26)),
        ("parietal_sup_L", "Parietal_Sup_L", "parietal", P, (-0.40, 0.55, -0.35), (0.32, 0.30, 0.36)),
        ("parietal_sup_R", "Parietal_Sup_R", "parietal", P, (0.40, 0.55, -0.35), (0.32, 0.30, 0.36)),
        ("precuneus_L", "Precuneus_L", "parietal", P, (-0.22, 0.35, -0.55), (0.24, 0.32, 0.30)),
        ("precuneus_R", "Precuneus_R", "parietal", P, (0.22, 0.35, -0.55), (0.24, 0.32, 0.30)),
        ("temporal_sup_L", "Temporal_Sup_L", "temporal", T, (-0.62, -0.25, 0.05), (0.22, 0.24, 0.42)),
        ("temporal_sup_R", "Temporal_Sup_R", "temporal", T, (0.62, -0.25, 0.05), (0.22, 0.24, 0.42)),
        ("temporal_mid_L", "Temporal_Mid_L", "temporal", T, (-0.55, -0.50, -0.05), (0.24, 0.22, 0.38)),
        ("temporal_mid_R", "Temporal_Mid_R", "temporal", T, (0.55, -0.50, -0.05), (0.24, 0.22, 0.38)),
        ("occipital_L", "Occipital_Mid_L", "occipital", O, (-0.35, 0.10, -0.80), (0.30, 0.38, 0.30)),
        ("occipital_R", "Occipital_Mid_R", "occipital", O, (0.35, 0.10, -0.80), (0.30, 0.38, 0.30)),
        ("insula_L", "Insula_L", "subcortical", S, (-0.38, 0.0, 0.10), (0.16, 0.20, 0.22)),
        ("insula_R", "Insula_R", "subcortical", S, (0.38, 0.0, 0.10), (0.16, 0.20, 0.22)),
        ("thalamus_L", "Thalamus_L", "subcortical", S, (-0.14, 0.02, -0.10), (0.13, 0.15, 0.16)),
        ("thalamus_R", "Thalamus_R", "subcortical", S, (0.14, 0.02, -0.10), (0.13, 0.15, 0.16)),
        ("hippocampus_L", "Hippocampus_L", "limbic", (235, 150, 150), (-0.22, -0.28, -0.15), (0.11, 0.12, 0.24)),
        ("hippocampus_R", "Hippocampus_R", "limbic", (235, 150, 150), (0.22, -0.28, -0.15), (0.11, 0.12, 0.24)),
        ("amygdala_L", "Amygdala_L", "limbic", (240, 130, 130), (-0.20, -0.18, 0.18), (0.10, 0.11, 0.11)),
        ("amygdala_R", "Amygdala_R", "limbic", (240, 130, 130), (0.20, -0.18, 0.18), (0.10, 0.11, 0.11)),
        ("caudate_L", "Caudate_L", "subcortical", S, (-0.16, 0.22, 0.10), (0.10, 0.16, 0.20)),
        ("caudate_R", "Caudate_R", "subcortical", S, (0.16, 0.22, 0.10), (0.10, 0.16, 0.20)),
        ("cerebellum_L", "Cerebellum_6_L", "cerebellum", C, (-0.32, -0.62, -0.55), (0.30, 0.24, 0.28)),
        ("cerebellum_R", "Cerebellum_6_R", "cerebellum", C, (0.32, -0.62, -0.55), (0.30, 0.24, 0.28)),
        ("vermis", "Vermis_7", "cerebellum", C, (0.0, -0.55, -0.60), (0.14, 0.18, 0.20)),
        ("pons", "Brainstem_Pons", "brainstem", B, (0.0, -0.30, 0.05), (0.16, 0.18, 0.16)),
        ("medulla", "Brainstem_Medulla", "brainstem", B, (0.0, -0.55, -0.05), (0.12, 0.20, 0.13)),
        ("midbrain", "Brainstem_Midbrain", "brainstem", B, (0.0, -0.10, -0.05), (0.13, 0.14, 0.13)),
    ]
    return defs


def build_procedural_regions() -> dict[str, Region]:
    regions: dict[str, Region] = {}
    for rid, name, system, color, center, radii in _procedural_defs():
        mesh = make_ellipsoid(*radii)
        c = np.array(center, dtype=np.float32)
        if abs(float(c[0])) < 0.45 and system not in ("brainstem",):
            c[0] += 0.07 if c[0] >= 0 else -0.07
        regions[rid] = Region(
            id=rid, name=name, system=system, color=tuple(color),
            mesh=mesh, base_center=c,
        )
    return regions


def load_regions(manifest_path: str | None = None) -> dict[str, Region]:
    if manifest_path and os.path.exists(manifest_path):
        with open(manifest_path) as f:
            man = json.load(f)
        regions: dict[str, Region] = {}
        base = os.path.dirname(os.path.abspath(manifest_path))
        for item in man.get("regions", []):
            mesh_file = os.path.join(base, item["mesh"]) if item.get("mesh") else ""
            if os.path.exists(mesh_file) and mesh_file.endswith(".npz"):
                d = np.load(mesh_file)
                verts = d["verts"].astype(np.float32)
                faces = d["faces"].astype(np.int32)
                v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
                vol = float((v0 * np.cross(v1, v2)).sum() / 6.0)
                if vol < 0:
                    faces = faces[:, ::-1].copy()
                mesh = Mesh(verts=verts, faces=faces,
                            color=tuple(item.get("color", [120, 140, 200])))
            else:
                radii = tuple(item.get("radii", [0.2, 0.2, 0.2]))
                mesh = make_ellipsoid(*radii)
                mesh.color = tuple(item.get("color", [120, 140, 200]))
            regions[item["id"]] = Region(
                id=item["id"], name=item.get("name", item["id"]),
                system=item.get("system", "unknown"),
                color=tuple(item.get("color", [120, 140, 200])),
                mesh=mesh,
                base_center=np.array(item.get("center", [0, 0, 0]), dtype=np.float32),
            )
        if regions:
            return regions
    return build_procedural_regions()
