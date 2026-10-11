from __future__ import annotations
import argparse, json, os

SYSTEM_MAP = {
    "Precentral": "frontal", "Frontal": "frontal", "Rectus": "frontal",
    "Olfactory": "frontal", "Rolandic": "frontal", "Supp_Motor": "frontal",
    "Insula": "insular", "Cingulum": "limbic", "Hippocampus": "limbic",
    "ParaHippocampal": "limbic", "Amygdala": "limbic",
    "Calcarine": "occipital", "Cuneus": "occipital", "Lingual": "occipital",
    "Occipital": "occipital", "Fusiform": "temporal",
    "Postcentral": "parietal", "Parietal": "parietal", "SupraMarginal": "parietal",
    "Angular": "parietal", "Precuneus": "parietal", "Paracentral": "parietal",
    "Caudate": "subcortical", "Putamen": "subcortical", "Pallidum": "subcortical",
    "Thalamus": "subcortical", "Heschl": "temporal", "Temporal": "temporal",
    "Cerebellum": "cerebellum", "Vermis": "cerebellum", "Brainstem": "brainstem",
}

PALETTE = {
    "frontal": [86, 140, 230], "parietal": [86, 200, 170], "temporal": [230, 170, 80],
    "occipital": [200, 110, 220], "limbic": [235, 130, 130], "subcortical": [235, 120, 120],
    "insular": [240, 160, 110], "cerebellum": [140, 180, 120], "brainstem": [180, 170, 160],
    "unknown": [150, 150, 180],
}

def system_for(name: str) -> str:
    for k, v in SYSTEM_MAP.items():
        if name.startswith(k):
            return v
    return "unknown"

def build_procedural_manifest(out: str):
    from brain_tui.atlas import _procedural_defs
    regions = []
    for rid, name, system, color, center, radii in _procedural_defs():
        regions.append({"id": rid, "name": name, "system": system,
                        "color": list(color), "center": list(center), "radii": list(radii)})
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump({"atlas": "procedural-36", "regions": regions}, open(out, "w"), indent=2)
    print(f"wrote {out} ({len(regions)} procedural regions)")

def fetch_aal(out: str, max_tris: int = 3000):
    try:
        from nilearn.datasets import fetch_atlas_aal
        import nibabel as nib
        import numpy as np
        from skimage.measure import marching_cubes
    except ImportError as e:
        raise SystemExit(f"missing dep for atlas fetch: {e}\n pip install nilearn nibabel scikit-image trimesh")
    print("downloading AAL116 via nilearn…")
    aal = fetch_atlas_aal(version="SPM12")
    img = nib.load(aal.maps)
    data = np.asanyarray(img.dataobj)
    labels: list[str] = list(aal.labels)
    values = sorted(int(v) for v in np.unique(data) if int(v) != 0)
    assert len(values) >= len(labels) - 1, f"{len(values)} values vs {len(labels)-1} labels"
    import trimesh
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    meshdir = os.path.join(base, "assets", "meshes")
    os.makedirs(meshdir, exist_ok=True)
    regions: list[dict] = []
    A = np.array(img.affine, dtype=np.float64)
    R = A[:3, :3]
    T = A[:3, 3]

    def idx_to_mni(pts_idx: np.ndarray) -> np.ndarray:
        return pts_idx @ R.T + T

    def mni_to_world(p: np.ndarray) -> np.ndarray:
        """MNI (x right, y front, z up) -> ours (x right, y up, z front)."""
        return np.stack([p[..., 0], p[..., 2], p[..., 1]], axis=-1)

    for idx, name in enumerate(labels):
        if idx == 0:
            continue
        mask = (data == values[idx - 1])
        if mask.sum() < 50:
            continue
        m = mask.astype(np.uint8)
        try:
            verts, faces, _, _ = marching_cubes(m, level=0.5)
        except Exception as e:
            print(f"skip {name}: {e}")
            continue
        verts_mni = idx_to_mni(verts.astype(np.float64))
        verts_w = mni_to_world(verts_mni).astype(np.float32)
        verts_w -= verts_w.mean(axis=0)
        mesh = trimesh.Trimesh(vertices=verts_w, faces=faces, process=True)
        try:
            mesh.remove_infinite_values()
            trimesh.smoothing.filter_taubin(mesh, iterations=8)
        except Exception:
            pass
        try:
            mesh = mesh.simplify_quadric_decimation(max_tris)
        except Exception:
            pass
        v = np.asarray(mesh.vertices, dtype=np.float32)
        v -= v.mean(axis=0)
        rid = name.replace(" ", "_")
        np.savez_compressed(os.path.join(meshdir, f"{rid}.npz"),
                            verts=v / 90.0, faces=np.asarray(mesh.faces, dtype=np.int32))
        ii = np.column_stack(np.nonzero(mask)).astype(np.float64)
        c_mm = idx_to_mni(ii.mean(axis=0))
        c_world = mni_to_world(c_mm) / 90.0
        sys = system_for(name)
        regions.append({"id": rid, "name": name, "system": sys,
                        "color": PALETTE.get(sys, PALETTE["unknown"]),
                        "center": c_world.tolist(),
                        "mesh": f"../assets/meshes/{rid}.npz"})
        print(f"  {rid}: {len(mesh.faces)} tris")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump({"atlas": "AAL116", "regions": regions}, open(out, "w"), indent=2)
    print(f"wrote {out} ({len(regions)} regions)")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--atlas", default="procedural", choices=["procedural", "AAL116"])
    p.add_argument("--out", default="data/manifest.json")
    p.add_argument("--max-tris", type=int, default=3000)
    args = p.parse_args()
    if args.atlas == "AAL116":
        fetch_aal(args.out, args.max_tris)
    else:
        build_procedural_manifest(args.out)

if __name__ == "__main__":
    main()
