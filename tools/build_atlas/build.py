from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np

from cns_atlas.knowledge import KnowledgeError, load_references
from cns_atlas.meshes import LODS, MeshData
from cns_atlas.model import Structure

from .fetch import DEFAULT_CACHE, fetch, member_path
from .hierarchy import build_tree, load_structures, with_xrefs
from .idlock import IdLock, load_lock, write_lock
from .labels import (crop, load_label_image, mapping_for, merge, read_label_names, relabel,
                     source_values)
from .meshing import levels, surface
from .recipe import BuildError, Recipe, VolumeSpec, load_recipe
from .templates import covers, on_grid, to_uint8
from .tracts import place
from .validate import (check_hierarchy, check_ids, check_knowledge, check_sources,
                       check_templates, check_voxels)
from .writer import write_package


def present(data: np.ndarray) -> set[int]:
    return set(np.unique(data).tolist()) - {0}


def build_report(recipe: Recipe, structures: list[Structure], meshes: list[dict[int, MeshData]],
                 volumes: list[tuple[VolumeSpec, np.ndarray, np.ndarray]], templates=(),
                 tracts=None, shape_only=(), per_source=None) -> str:
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
    lines += [f"- template for {name}: shape {list(data.shape)}, uint8"
              for name, data, _ in templates]
    lines += [f"- source {name}: {count} structures" for name, count in (per_source or {}).items()]
    if tracts is not None:
        _, rows = tracts
        lines.append(f"- tracts: {len(rows)}, voxels {sum(len(flat) for _, flat in rows)}")
    for spec in (*recipe.sources, *recipe.tracts):
        if spec.drop:
            lines.append(f"- dropped from {spec.source.id}: "
                         f"{', '.join(str(value) for value in spec.drop)}")
    if shape_only:
        lines.append(f"- 3D shape only, no voxels at label resolution: {', '.join(shape_only)}")
    return "\n".join(lines) + "\n"


def _replaceable(out: Path) -> bool:
    if not out.exists():
        return True
    if not out.is_dir():
        return False
    if not any(out.iterdir()):
        return True
    try:
        metadata = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(metadata, dict) and "format_version" in metadata


def build(src: Path, out: Path, cache: Path = DEFAULT_CACHE, log=print) -> Path:
    src, out = Path(src), Path(out)
    if not _replaceable(out):
        raise BuildError([f"{out}: exists and is not an atlas package; refusing to replace it"])
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
    problems += check_templates(recipe, src)
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
        values = source_values(images[spec.source.id])
        mapped = set(mapping_for(spec.source.id, planned))
        dropped = set(spec.drop)
        problems += [f"source {spec.source.id}: label {value} has no structure"
                     for value in sorted(values - mapped - dropped)]
        problems += [f"source {spec.source.id}: drop value {value} is not in the source"
                     for value in sorted(dropped - values)]
    planned = with_xrefs(planned, names)
    volumes = []
    for vspec in recipe.volumes:
        layers = [(s.priority, images[s.source.id], mapping_for(s.source.id, planned))
                  for s in recipe.sources if s.volume == vspec.name]
        grid = images[vspec.grid_source]
        volumes.append((vspec, merge(grid, layers), grid.affine))
    grids = {spec.name: (data.shape, affine) for spec, data, affine in volumes}
    natives = [crop(relabel(images[s.source.id], mapping_for(s.source.id, planned)),
                    images[s.source.id].affine)
               for s in recipe.sources if s.mesh_grid == "native"]
    native_ids = set().union(*(present(data) for data, _ in natives))
    tract_rows: list[tuple[int, np.ndarray]] = []
    for spec in recipe.tracts:
        shape, affine = grids[spec.labels]
        for p in planned:
            for ref in p.labels:
                if ref.source == spec.source.id:
                    log(f"fetching {spec.source.id} {ref.value}")
                    image = nib.load(fetch(spec.file_spec(ref.value), cache))
                    flat = place(image, shape, affine, f"tracts {spec.source.id}: {ref.value}")
                    tract_rows.append((p.structure.id, flat))
    tract_ids = {structure_id for structure_id, flat in tract_rows if len(flat)}
    label_ids = set().union(*(present(data) for _, data, _ in volumes))
    shape_only = [p.structure.name for p in planned if p.structure.id in native_ids - label_ids]
    problems += check_voxels(planned, [data for _, data, _ in volumes],
                             spared=native_ids | tract_ids)
    if problems:
        raise BuildError(problems)
    templates = []
    for spec in recipe.templates:
        log(f"fetching {spec.source.id}")
        image = nib.load(member_path(spec, fetch(spec, cache), spec.member))
        shape, affine = grids[spec.volume]
        if not covers(image, shape, affine):
            raise BuildError([f"template {spec.source.id} does not cover volume {spec.volume}"])
        templates.append((spec.volume, to_uint8(on_grid(image, shape, affine)), affine))

    log("meshing")
    jobs = [(data, affine, present(data)) for data, affine in natives]
    jobs += [(data, affine, present(data) - native_ids) for _, data, affine in volumes]
    tracts = None
    if recipe.tracts:
        name = recipe.tracts[0].labels
        shape, affine = grids[name]
        tracts = (name, tract_rows)
        for structure_id, flat in tract_rows:
            mask = np.zeros(shape, dtype=np.uint16)
            mask.flat[flat] = structure_id
            jobs.append((mask, affine, {structure_id}))
    meshes: list[dict[int, MeshData]] = [{} for _ in recipe.lod_fractions]
    for data, affine, ids in jobs:
        for p in planned:
            if p.structure.id in ids:
                mesh = surface(data, affine, p.structure.id, recipe.smoothing_iterations,
                               recipe.smoothing_pass_band)
                built = levels(mesh, recipe.lod0_max_faces, recipe.lod_fractions,
                               recipe.min_faces)
                for level, mesh_data in zip(meshes, built):
                    level[p.structure.id] = mesh_data

    structures = [p.structure for p in planned]
    specs = (*recipe.sources, *recipe.templates, *recipe.tracts)
    licence_files = [src / s.licence_file for s in specs if s.licence_file]
    per_source = {spec.source.id: sum(any(ref.source == spec.source.id for ref in p.labels)
                                      for p in planned)
                  for spec in (*recipe.sources, *recipe.tracts)}
    report = build_report(recipe, structures, meshes, volumes, templates, tracts, shape_only,
                          per_source)
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}-", dir=out.parent))
    try:
        package = staging / "package"
        write_package(package, recipe, structures, [s.source for s in specs], volumes, meshes,
                      src / "knowledge", licence_files, report, templates, tracts)
        previous = staging / "previous"
        if out.exists():
            out.replace(previous)
        try:
            package.replace(out)
        except OSError:
            if previous.exists():
                previous.replace(out)
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    write_lock(src / "ids.lock", IdLock(lock.published | {s.id for s in structures}, lock.retired))
    log(f"wrote {out}")
    return out
