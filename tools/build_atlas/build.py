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
from .hierarchy import (build_tree, load_structures, resolve_members, with_xrefs,
                        without_sources)
from .idlock import IdLock, load_lock, write_lock
from .labels import (crop, load_label_image, load_members, mapping_for, merge,
                     read_label_names, relabel, source_values)
from .meshing import levels, surface
from .pathways import check_pathway_texts, check_pathways, for_package, load_pathways
from .recipe import BuildError, Recipe, VolumeSpec, load_recipe
from .templates import covers, on_grid, to_uint8
from .timelines import load_timelines
from .tracts import place
from .validate import (check_hierarchy, check_ids, check_knowledge, check_sources,
                       check_templates, check_voxels)
from .writer import write_package


def present(data: np.ndarray) -> set[int]:
    return set(np.unique(data).tolist()) - {0}


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def build_report(recipe: Recipe, structures: list[Structure], meshes: list[dict[int, MeshData]],
                 volumes: list[tuple[VolumeSpec, np.ndarray, np.ndarray]], templates=(),
                 tracts=None, shape_only=(), per_source=None, pathways: int = 0,
                 local_note: str = "", sources=None, repaired: int = 0,
                 overlaps: dict[str, int] | None = None) -> str:
    kinds: dict[str, int] = {}
    for s in structures:
        kinds[s.kind] = kinds.get(s.kind, 0) + 1
    lines = [f"# Build report: {recipe.name} {recipe.version}", "",
             f"- structures: {len(structures)}"]
    lines += [f"- {kind}: {count}" for kind, count in sorted(kinds.items())]
    lines.append(f"- with geometry: {len(meshes[0])}")
    lines.append(f"- pathways: {pathways}")
    lines += [f"- {name} faces: {sum(len(m.faces) for m in level.values())}"
              for name, level in zip(LODS, meshes)]
    lines += [f"- volume {spec.name}: shape {list(data.shape)}, space {spec.space}"
              for spec, data, _ in volumes]
    lines += [f"- template for {name}: shape {list(data.shape)}, uint8"
              for name, data, _ in templates]
    lines += [f"- source {name}: {plural(count, 'structure')}"
              for name, count in (per_source or {}).items()]
    if tracts is not None:
        _, rows = tracts
        lines.append(f"- tracts: {len(rows)}, voxels {sum(len(flat) for _, flat in rows)}")
    for spec in (*(recipe.sources if sources is None else sources), *recipe.tracts):
        if spec.drop:
            lines.append(f"- dropped from {spec.source.id}: "
                         f"{', '.join(str(value) for value in spec.drop)}")
    lines += [f"- overlapping voxels in {name}: {count}"
              for name, count in (overlaps or {}).items()]
    warnings = []
    if repaired:
        warnings.append(f"{plural(repaired, 'vertex normal')} repaired")
    if shape_only:
        warnings.append(f"3D shape only, no voxels at label resolution: {', '.join(shape_only)}")
    lines.append("- warnings:" if warnings else "- warnings: none")
    lines += [f"  - {w}" for w in warnings]
    if local_note:
        lines.append(local_note)
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


def build(src: Path, out: Path, cache: Path = DEFAULT_CACHE, log=print,
          local: bool = False) -> Path:
    src, out = Path(src), Path(out)
    if not _replaceable(out):
        raise BuildError([f"{out}: exists and is not an atlas package; refusing to replace it"])
    recipe = load_recipe(src / "recipe.toml")
    raws = load_structures(src / "structures.toml")
    lock = load_lock(src / "ids.lock")
    pathways = load_pathways(src / "pathways.toml")
    references_path = src / "knowledge" / "references.toml"
    if not references_path.exists():
        raise BuildError([f"{references_path}: file is missing"])
    try:
        references = load_references(references_path)
    except KnowledgeError as exc:
        raise BuildError([str(exc)]) from exc
    timelines = load_timelines(src / "timelines", pathways, references)
    problems = check_hierarchy(raws) + check_ids(raws, lock) + check_sources(raws, recipe, src)
    problems += check_templates(recipe, src)
    problems += check_knowledge(src / "knowledge", references, {r.id: r.concept for r in raws},
                                {f"pathway-{p.key}" for p in pathways})
    problems += check_pathway_texts(src / "knowledge", pathways)
    if problems:
        raise BuildError(problems)
    raws = resolve_members(raws, {s.source.id: s.member_values
                                  for s in recipe.sources if s.members})
    skipped = set() if local else {s.source.id for s in recipe.sources if s.local_only}
    sources = [s for s in recipe.sources if s.source.id not in skipped]
    planned = build_tree(without_sources(raws, skipped))
    left_out = {r.id for r in raws} - {p.structure.id for p in planned}
    problems = check_pathways(pathways, [p.structure for p in planned],
                              {p.structure.id for p in planned if p.labels}, left_out)
    if problems:
        raise BuildError(problems)

    images, names, overlaps = {}, {}, {}
    for spec in sources:
        log(f"fetching {spec.source.id}")
        archive = fetch(spec, cache)
        if spec.members:
            images[spec.source.id], overlaps[spec.source.id] = load_members(spec, archive)
        else:
            images[spec.source.id] = load_label_image(member_path(spec, archive, spec.member),
                                                       spec.mask, spec.source.id)
        if spec.label_names:
            names[spec.source.id] = read_label_names(member_path(spec, archive, spec.label_names))
    for spec in sources:
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
                  for s in sources if s.volume == vspec.name]
        grid = images[vspec.grid_source]
        volumes.append((vspec, merge(grid, layers), grid.affine))
    grids = {spec.name: (data.shape, affine) for spec, data, affine in volumes}
    natives = [crop(relabel(images[s.source.id], mapping_for(s.source.id, planned)),
                    images[s.source.id].affine)
               for s in sources if s.mesh_grid == "native"]
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
    repaired = 0
    for data, affine, ids in jobs:
        for p in planned:
            if p.structure.id in ids:
                mesh = surface(data, affine, p.structure.id, recipe.smoothing_iterations,
                               recipe.smoothing_pass_band)
                built, count = levels(mesh, recipe.lod0_max_faces, recipe.lod_fractions,
                                      recipe.min_faces)
                repaired += count
                for level, mesh_data in zip(meshes, built):
                    level[p.structure.id] = mesh_data

    structures = [p.structure for p in planned]
    problems = check_pathways(pathways, structures, set(meshes[0]), left_out)
    if problems:
        raise BuildError(problems)
    specs = (*sources, *recipe.templates, *recipe.tracts)
    licence_files = [src / s.licence_file for s in specs if s.licence_file]
    per_source = {spec.source.id: sum(any(ref.source == spec.source.id for ref in p.labels)
                                      for p in planned)
                  for spec in (*sources, *recipe.tracts)}
    included = [s.source.id for s in sources if s.local_only]
    if included:
        local_note = f"- local-only sources included: {', '.join(included)}"
    elif skipped:
        local_note = f"- local-only sources left out: {', '.join(sorted(skipped))}"
    else:
        local_note = ""
    report = build_report(recipe, structures, meshes, volumes, templates, tracts, shape_only,
                          per_source, len(pathways), local_note, sources, repaired,
                          overlaps=overlaps)
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}-", dir=out.parent))
    try:
        package = staging / "package"
        write_package(package, recipe, structures, [s.source for s in specs], volumes, meshes,
                      src / "knowledge", licence_files, report, templates, tracts,
                      for_package(pathways, {r.id: r.name for r in raws}, left_out), included,
                      timelines=timelines)
        size = sum(p.stat().st_size for p in package.rglob("*") if p.is_file())
        with (package / "build-report.md").open("a", encoding="utf-8") as report_file:
            report_file.write(f"- package size: {size / 1e6:.1f} MB\n")
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
    write_lock(src / "ids.lock", IdLock(lock.published | {r.id for r in raws}, lock.retired))
    log(f"wrote {out}")
    return out
