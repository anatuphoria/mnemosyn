from __future__ import annotations

import gzip
import io
import json
import shutil
from pathlib import Path

import nibabel as nib
import numpy as np

from cns_atlas.meshes import LODS, MeshData, write_lod
from cns_atlas.model import FORMAT_VERSION, Source, Structure

from .recipe import Recipe, VolumeSpec

OPPOSITE = {"R": "l", "L": "r", "A": "p", "P": "a", "S": "i", "I": "s"}


def write_json(path: Path, data) -> None:
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def write_volume(path: Path, data: np.ndarray, affine: np.ndarray, dtype=np.uint16) -> None:
    image = nib.Nifti1Image(data.astype(dtype), affine)
    image.set_data_dtype(dtype)
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz:
        gz.write(image.to_bytes())
    path.write_bytes(buffer.getvalue())


def orientation(affine: np.ndarray) -> str:
    return "".join(OPPOSITE[code] for code in nib.aff2axcodes(affine))


def write_package(out: Path, recipe: Recipe, structures: list[Structure], sources: list[Source],
                  volumes: list[tuple[VolumeSpec, np.ndarray, np.ndarray]],
                  meshes: list[dict[int, MeshData]], knowledge_src: Path,
                  licence_files: list[Path], report: str, templates=()) -> None:
    (out / "volumes").mkdir(parents=True)
    volume_records = []
    spaces = {spec.name: spec.space for spec, _, _ in volumes}
    for spec, data, affine in volumes:
        write_volume(out / "volumes" / f"{spec.name}.nii.gz", data, affine)
        volume_records.append({"file": f"volumes/{spec.name}.nii.gz", "space": spec.space,
                               "role": "labels", "affine_to_world": np.eye(4).tolist()})
    for name, data, affine in templates:
        write_volume(out / "volumes" / f"{name}-template.nii.gz", data, affine, dtype=np.uint8)
        volume_records.append({"file": f"volumes/{name}-template.nii.gz", "space": spaces[name],
                               "role": "template", "labels": name,
                               "affine_to_world": np.eye(4).tolist()})
    _, first_data, first_affine = volumes[0]
    write_json(out / "metadata.json", {
        "name": recipe.name,
        "citation": recipe.citation,
        "atlas_link": recipe.atlas_link,
        "species": recipe.species,
        "symmetric": False,
        "resolution": [round(float(z) * 1000.0, 3) for z in nib.affines.voxel_sizes(first_affine)],
        "orientation": orientation(first_affine),
        "shape": [int(n) for n in first_data.shape[:3]],
        "version": recipe.version,
        "additional_references": [f"https://doi.org/{s.doi}" if s.doi else s.url for s in sources],
        "format_version": FORMAT_VERSION,
        "coordinate_units": "mm",
        "licence": recipe.licence,
        "volumes": volume_records,
    })
    write_json(out / "structures.json", [s.to_json() for s in structures])
    write_json(out / "sources.json", [s.to_json() for s in sources])
    write_json(out / "collections.json", [])
    write_json(out / "pathways.json", [])
    for name, level in zip(LODS, meshes):
        write_lod(out / "meshes" / name, level)
    shutil.copytree(knowledge_src, out / "knowledge")
    if licence_files:
        (out / "LICENSES").mkdir()
        for path in licence_files:
            shutil.copyfile(path, out / "LICENSES" / path.name)
    (out / "build-report.md").write_text(report, encoding="utf-8")
