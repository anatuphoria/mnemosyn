from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np

from cns_atlas.knowledge import KnowledgeError, load_references
from cns_atlas.meshes import LODS, MeshData
from cns_atlas.model import Structure

from .fetch import DEFAULT_CACHE, fetch, member_path
from .hierarchy import build_tree, load_structures, with_xrefs
from .idlock import IdLock, load_lock, write_lock
from .labels import load_label_image, mapping_for, merge, read_label_names, source_values
from .meshing import levels, surface
from .recipe import BuildError, Recipe, VolumeSpec, load_recipe
from .validate import check_hierarchy, check_ids, check_knowledge, check_sources, check_voxels
from .writer import write_package


def build_report(recipe: Recipe, structures: list[Structure], meshes: list[dict[int, MeshData]],
                 volumes: list[tuple[VolumeSpec, np.ndarray, np.ndarray]]) -> str:
    kinds: dict[str, int] = {}
    for s in structures:
        kinds[s.kind] = kinds.get(s.kind, 0) + 1
    lines = [f"# Build report: {recipe.name} {recipe.version}", "",
             f"- structures: {len(structures)}"]
    lines += [f"- {kind}: {count}" for kind, count in sorted(kinds.items())]
    lines.append(f"- with geometry: {len(meshes[0])}")
    lines += [f"- {name} faces: {sum(len(m.faces) for m in level.values())}"
              for name, level in zip(LODS, meshes)]
    lines += [f"- volume {spec.name}: shape {list(data.shape)}, space {spec.space}"
              for spec, data, _ in volumes]
    return "\n".join(lines) + "\n"


def build(src: Path, out: Path, cache: Path = DEFAULT_CACHE, log=print) -> Path:
    src, out = Path(src), Path(out)
    recipe = load_recipe(src / "recipe.toml")
    raws = load_structures(src / "structures.toml")
    lock = load_lock(src / "ids.lock")
    references_path = src / "knowledge" / "references.toml"
    if not references_path.exists():
        raise BuildError([f"{references_path}: file is missing"])
    try:
        references = load_references(references_path)
    except KnowledgeError as exc:
        raise BuildError([str(exc)]) from exc
    problems = check_hierarchy(raws) + check_ids(raws, lock) + check_sources(raws, recipe, src)
    problems += check_knowledge(src / "knowledge", references, {r.id: r.concept for r in raws},
                                set())
    if problems:
        raise BuildError(problems)
    planned = build_tree(raws)

    images, names = {}, {}
    for spec in recipe.sources:
        log(f"fetching {spec.source.id}")
        archive = fetch(spec, cache)
        images[spec.source.id] = load_label_image(member_path(spec, archive, spec.member))
        if spec.label_names:
            names[spec.source.id] = read_label_names(member_path(spec, archive, spec.label_names))
    for spec in recipe.sources:
        mapped = set(mapping_for(spec.source.id, planned))
        problems += [f"source {spec.source.id}: label {value} has no structure"
                     for value in sorted(source_values(images[spec.source.id]) - mapped)]
    planned = with_xrefs(planned, names)
    volumes = []
    for vspec in recipe.volumes:
        layers = [(s.priority, images[s.source.id], mapping_for(s.source.id, planned))
                  for s in recipe.sources if s.volume == vspec.name]
        grid = images[vspec.grid_source]
        volumes.append((vspec, merge(grid, layers), grid.affine))
    problems += check_voxels(planned, [data for _, data, _ in volumes])
    if problems:
        raise BuildError(problems)

    log("meshing")
    meshes: list[dict[int, MeshData]] = [{} for _ in recipe.lod_fractions]
    for _, data, affine in volumes:
        present = set(np.unique(data).tolist())
        for p in planned:
            if p.labels and p.structure.id in present:
                mesh = surface(data, affine, p.structure.id, recipe.smoothing_iterations,
                               recipe.smoothing_pass_band)
                built = levels(mesh, recipe.lod0_max_faces, recipe.lod_fractions,
                               recipe.min_faces)
                for level, mesh_data in zip(meshes, built):
                    level[p.structure.id] = mesh_data

    structures = [p.structure for p in planned]
    licence_files = [src / s.licence_file for s in recipe.sources if s.licence_file]
    report = build_report(recipe, structures, meshes, volumes)
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}-", dir=out.parent))
    try:
        package = staging / "package"
        write_package(package, recipe, structures, [s.source for s in recipe.sources], volumes,
                      meshes, src / "knowledge", licence_files, report)
        if out.exists():
            out.replace(staging / "previous")
        package.replace(out)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    write_lock(src / "ids.lock", IdLock(lock.published | {s.id for s in structures}, lock.retired))
    log(f"wrote {out}")
    return out
