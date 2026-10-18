from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np
from nibabel.processing import resample_from_to

from .fetch import member_path
from .hierarchy import PlannedStructure
from .recipe import BuildError, SourceSpec


def read_label_names(path: Path) -> dict[int, str]:
    names = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit():
            names[int(parts[0])] = parts[1]
    return names


CROP_SLAB = 32


def _box(proxy) -> tuple[np.ndarray, np.ndarray] | None:
    lo = hi = None
    for z in range(0, proxy.shape[2], CROP_SLAB):
        index = np.argwhere(np.nan_to_num(np.asarray(proxy[:, :, z:z + CROP_SLAB])) != 0)
        if len(index):
            index[:, 2] += z
            lo = index.min(axis=0) if lo is None else np.minimum(lo, index.min(axis=0))
            hi = index.max(axis=0) if hi is None else np.maximum(hi, index.max(axis=0))
    return None if lo is None else (lo, hi)


def load_label_image(path: Path, mask: bool = False, name: str = "", cropped: bool = False,
                     threshold: float | None = None, margin: float = 0.0) -> nib.Nifti1Image:
    image = nib.load(path, keep_file_open=True) if cropped else nib.load(path)
    affine = image.affine
    if cropped:
        box = _box(image.dataobj)
        if box is None:
            raise BuildError([f"source {name}: has no labels"])
        pad = np.ceil(margin / np.asarray(image.header.get_zooms()[:3], dtype=float)).astype(int)
        lo = np.maximum(box[0] - 1 - pad, 0)
        hi = np.minimum(box[1] + 2 + pad, image.shape[:3])
        data = np.asarray(image.dataobj[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]])
        shift = np.eye(4)
        shift[:3, 3] = lo
        affine = np.asarray(affine) @ shift
    else:
        data = np.asarray(image.dataobj)
    if mask:
        data = np.nan_to_num(data)
        data = data >= threshold if threshold is not None else data != 0
    elif not np.issubdtype(data.dtype, np.integer) and np.any(data != np.rint(data)):
        raise BuildError([f"source {name}: label values are not whole numbers; set mask = true"])
    return nib.Nifti1Image(data.astype(np.int32), affine)


def load_parts(path: Path, parts: tuple[int, ...], threshold: float, name: str = ""
               ) -> nib.Nifti1Image:
    image = nib.load(path)
    if len(image.shape) != 4:
        raise BuildError([f"source {name}: parts need a 4D probability image"])
    data = np.nan_to_num(np.asarray(image.dataobj, dtype=np.float32))
    inside = data[..., 1:].sum(axis=-1) >= threshold
    best = np.asarray(parts)[data[..., list(parts)].argmax(axis=-1)]
    return nib.Nifti1Image(np.where(inside, best, 0).astype(np.int32), image.affine)


def trim_against(image: nib.Nifti1Image, data: np.ndarray, affine: np.ndarray,
                 allowed: set[int] | None) -> nib.Nifti1Image:
    values = np.asarray(image.dataobj).copy()
    index = np.argwhere(values > 0)
    world = np.c_[index, np.ones(len(index))] @ np.asarray(image.affine).T
    other = np.rint(world @ np.linalg.inv(affine).T)[:, :3].astype(int)
    inside = ((other >= 0) & (other < data.shape)).all(axis=1)
    labels = np.zeros(len(index), dtype=data.dtype)
    labels[inside] = data[tuple(other[inside].T)]
    clear = labels > 0
    if allowed is not None:
        clear &= ~np.isin(labels, sorted(allowed))
    values[tuple(index[clear].T)] = 0
    return nib.Nifti1Image(values, image.affine)


def _world_z(image: nib.Nifti1Image, index: np.ndarray) -> np.ndarray:
    return (np.c_[index, np.ones(len(index))] @ np.asarray(image.affine).T)[:, 2]


def z_extent(image: nib.Nifti1Image) -> tuple[float, float]:
    z = _world_z(image, np.argwhere(np.asarray(image.dataobj) > 0))
    half = abs(np.asarray(image.affine)[2, :3]).sum() / 2
    return float(z.min() - half), float(z.max() + half)


def clip_z(image: nib.Nifti1Image, low: float, high: float) -> nib.Nifti1Image:
    values = np.asarray(image.dataobj).copy()
    index = np.argwhere(values != 0)
    z = _world_z(image, index)
    values[tuple(index[(z < low) | (z > high)].T)] = 0
    return nib.Nifti1Image(values, image.affine)


def member_masks(spec: SourceSpec, archive: Path):
    shape, affine = None, None
    for value, (name, member) in enumerate(spec.members, 1):
        image = nib.load(member_path(spec, archive, member))
        if shape is None:
            shape, affine = image.shape[:3], image.affine
        elif image.shape[:3] != shape or not np.allclose(image.affine, affine):
            raise BuildError([f"source {spec.source.id}: member {name} is on another grid"])
        values = np.nan_to_num(np.asarray(image.dataobj)).reshape(shape)
        inside = values >= spec.threshold if spec.threshold is not None else values != 0
        yield value, inside, affine


def load_tiles(spec: SourceSpec, archive: Path, sides: dict[int, str]) -> nib.Nifti1Image:
    shape = affine = total = best = arg = None
    for value, (name, member) in enumerate(spec.members, 1):
        image = nib.load(member_path(spec, archive, member))
        if shape is None:
            shape, affine = image.shape[:3], image.affine
            total, best = np.zeros(shape, np.float32), np.zeros(shape, np.float32)
            arg, split = np.zeros(shape, np.int32), np.zeros(shape, bool)
        elif image.shape[:3] != shape or not np.allclose(image.affine, affine):
            raise BuildError([f"source {spec.source.id}: member {name} is on another grid"])
        values = np.nan_to_num(np.asarray(image.dataobj, dtype=np.float32)).reshape(shape)
        total += values
        higher = values > best
        best[higher], arg[higher], split[higher] = values[higher], value, False
        tied = np.argwhere((values == best) & (values > 0) & ~higher)
        if len(tied) and sides.get(value) in ("left", "right"):
            x = (np.c_[tied, np.ones(len(tied))] @ np.asarray(affine).T)[:, 0]
            side = np.where(x < 0, "left", np.where(x > 0, "right", ""))
            held = np.array([sides.get(int(v), "") for v in arg[tuple(tied.T)]])
            take = tied[(side == sides[value]) & (held != side)]
            arg[tuple(take.T)] = value
            opposite = {"left": "right", "right": "left"}[sides[value]]
            split[tuple(tied[(side == "") & (held == opposite)].T)] = True
    return nib.Nifti1Image(np.where((total >= spec.tiles) & (best > 0) & ~split, arg, 0)
                           .astype(np.int32),
                           affine)


def _member_values(spec: SourceSpec, archive: Path):
    shape = affine = None
    for value, (name, member) in enumerate(spec.members, 1):
        image = nib.load(member_path(spec, archive, member))
        if shape is None:
            shape, affine = image.shape[:3], image.affine
        elif image.shape[:3] != shape or not np.allclose(image.affine, affine):
            raise BuildError([f"source {spec.source.id}: member {name} is on another grid"])
        yield value, np.nan_to_num(np.asarray(image.dataobj, dtype=np.float32)).reshape(shape)


def tile_fields(spec: SourceSpec, archive: Path, tiles: nib.Nifti1Image, wanted: set[int],
                extent: tuple[float, float] | None = None
                ) -> list[tuple[int, np.ndarray, np.ndarray]]:
    """Positive inside a member's tile: its probability minus the strongest other, bounded by the
    summed probability over the tile threshold; the zero level is a smooth tile border."""
    total = best = second = arg = None
    for value, values in _member_values(spec, archive):
        if total is None:
            total, best, second = (np.zeros(values.shape, np.float32) for _ in range(3))
            arg = np.zeros(values.shape, np.int32)
        total += values
        higher = values > best
        second = np.where(higher, best, np.maximum(second, values))
        best[higher], arg[higher] = values[higher], value
    labels = np.asarray(tiles.dataobj)
    affine = np.asarray(tiles.affine)
    out = []
    for value, values in _member_values(spec, archive):
        index = np.argwhere(labels == value)
        if value not in wanted or not len(index):
            continue
        lo = np.maximum(index.min(axis=0) - 2, 0)
        hi = np.minimum(index.max(axis=0) + 3, labels.shape)
        box = tuple(slice(a, b) for a, b in zip(lo, hi))
        others = np.where(arg[box] == value, second[box], best[box])
        field = np.minimum(values[box] - others, total[box] - spec.tiles)
        shift = np.eye(4)
        shift[:3, 3] = lo
        if extent is not None:
            axes = [np.arange(a, b).reshape([-1 if k == n else 1 for k in range(3)])
                    for n, (a, b) in enumerate(zip(lo, hi))]
            z = sum(affine[2, n] * axes[n] for n in range(3)) + affine[2, 3]
            field = np.where((z < extent[0]) | (z > extent[1]), -1.0, field)
        out.append((value, field.astype(np.float32), affine @ shift))
    return out


def separate_natives(spec: SourceSpec, archive: Path, mapping: dict[int, int],
                     extent: tuple[float, float] | None = None
                     ) -> list[tuple[np.ndarray, np.ndarray]]:
    natives = []
    for value, inside, affine in member_masks(spec, archive):
        if value in mapping:
            if extent is not None:
                inside = np.asarray(clip_z(nib.Nifti1Image(inside.astype(np.uint8), affine),
                                           *extent).dataobj) > 0
            data, cropped_affine = crop(inside, affine)
            natives.append((data.astype(np.uint16) * mapping[value], cropped_affine))
    return natives


def load_members(spec: SourceSpec, archive: Path) -> tuple[nib.Nifti1Image, int]:
    out, affine, lost = None, None, 0
    for value, inside, affine in member_masks(spec, archive):
        if out is None:
            out = np.zeros(inside.shape, dtype=np.int32)
        lost += int((inside & (out != 0)).sum())
        out[inside & (out == 0)] = value
    return nib.Nifti1Image(out, affine), lost


def source_values(image: nib.Nifti1Image) -> set[int]:
    return set(np.unique(np.asarray(image.dataobj)).tolist()) - {0}


def mapping_for(source_id: str, planned: list[PlannedStructure]) -> dict[int, int]:
    return {ref.value: p.structure.id for p in planned for ref in p.labels
            if ref.source == source_id}


def relabel(image: nib.Nifti1Image, mapping: dict) -> np.ndarray:
    values = np.asarray(image.dataobj)
    if not np.issubdtype(values.dtype, np.integer):
        values = np.rint(values)
    values = np.clip(values, 0, None).astype(np.int32, copy=False)
    lookup = np.zeros(int(values.max(initial=0)) + 1, dtype=np.uint16)
    for value, structure_id in mapping.items():
        if isinstance(value, int) and 0 <= value < len(lookup):
            lookup[value] = structure_id
    return lookup[values]


def crop(data: np.ndarray, affine: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    index = np.argwhere(data > 0)
    if not len(index):
        return data, affine
    lo, hi = index.min(axis=0), index.max(axis=0) + 1
    shift = np.eye(4)
    shift[:3, 3] = lo
    return data[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]], np.asarray(affine) @ shift


def merge(grid: nib.Nifti1Image, layers: list[tuple[int, nib.Nifti1Image, dict[int, int]]]
          ) -> np.ndarray:
    out = np.zeros(grid.shape[:3], dtype=np.uint16)
    for _, image, mapping in sorted(layers, key=lambda layer: layer[0]):
        if image.shape[:3] != grid.shape[:3] or not np.allclose(image.affine, grid.affine):
            image = resample_from_to(image, (grid.shape[:3], grid.affine), order=0)
        mapped = relabel(image, mapping)
        out[mapped > 0] = mapped[mapped > 0]
    return out
