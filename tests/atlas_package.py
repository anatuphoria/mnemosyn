import json
from pathlib import Path

import nibabel as nib
import numpy as np

from cns_atlas.meshes import MeshData, write_lod
from cns_atlas.model import FORMAT_VERSION, Source, Structure


def tetra(offset: float = 0.0) -> MeshData:
    vertices = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]], dtype=np.float32) + offset
    normals = np.array([[-1, -1, -1], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float16)
    faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]], dtype=np.uint32)
    return MeshData(vertices, normals, faces)


def tiny_structures() -> list[Structure]:
    blue, red, grey = (90, 140, 230), (230, 120, 120), (170, 170, 180)
    return [
        Structure(1, "CNS", "Central nervous system", (1,), grey, kind="group"),
        Structure(2, "Br", "Brain", (1, 2), grey, kind="group"),
        Structure(100, "ALG", "Alpha gyrus", (1, 2, 100), blue, synonyms=("first gyrus",)),
        Structure(101, "ALG-L", "Alpha gyrus (left)", (1, 2, 100, 101), blue, side="left",
                  concept=100, synonyms=("left Alpha gyrus",), xrefs={"toy": "Alpha_L"},
                  sources=("toy",)),
        Structure(102, "ALG-R", "Alpha gyrus (right)", (1, 2, 100, 102), blue, side="right",
                  concept=100, synonyms=("right Alpha gyrus",), xrefs={"toy": "Alpha_R"},
                  sources=("toy",)),
        Structure(110, "BEN", "Beta nucleus", (1, 2, 110), red, kind="nucleus", side="midline",
                  xrefs={"toy": "Beta"}, sources=("toy",)),
    ]


def write_package(root: Path, structures: list[Structure], *, meshes=None, lods=("lod0",),
                  volume=None, affine=None, sources=(), entries=None, references="",
                  format_version=FORMAT_VERSION, template=None, meshes_by_lod=None,
                  pathways=None, cells=None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    volumes = []
    if volume is not None:
        (root / "volumes").mkdir(exist_ok=True)
        grid = np.eye(4) if affine is None else affine
        nib.save(nib.Nifti1Image(volume.astype(np.uint16), grid), root / "volumes" / "brain.nii.gz")
        volumes.append({"file": "volumes/brain.nii.gz", "space": "MNI152",
                        "affine_to_world": np.eye(4).tolist()})
        if template is not None:
            nib.save(nib.Nifti1Image(template.astype(np.uint8), grid),
                     root / "volumes" / "brain-template.nii.gz")
            volumes.append({"file": "volumes/brain-template.nii.gz", "space": "MNI152",
                            "role": "template", "labels": "brain",
                            "affine_to_world": np.eye(4).tolist()})
    metadata = {"name": "test-atlas", "version": "0", "format_version": format_version,
                "volumes": volumes}
    (root / "metadata.json").write_text(json.dumps(metadata))
    (root / "structures.json").write_text(json.dumps([s.to_json() for s in structures]))
    (root / "sources.json").write_text(json.dumps([s.to_json() for s in sources]))
    (root / "collections.json").write_text("[]")
    (root / "pathways.json").write_text(json.dumps([p.to_json() for p in pathways or ()]))
    if cells is not None:
        (root / "cells.json").write_text(json.dumps([c.to_json() for c in cells]))
    if meshes_by_lod is not None:
        for name, level in meshes_by_lod.items():
            write_lod(root / "meshes" / name, level)
    else:
        for name in lods:
            write_lod(root / "meshes" / name, meshes or {})
    knowledge = root / "knowledge"
    knowledge.mkdir(exist_ok=True)
    (knowledge / "references.toml").write_text(references)
    for lang, by_target in (entries or {}).items():
        (knowledge / lang).mkdir(exist_ok=True)
        for target, text in by_target.items():
            (knowledge / lang / f"{target}.md").write_text(text)
    return root


TOY_SOURCE = Source("toy", "Toy labelled atlas", "Test A", 2024, "1", "CC0 1.0", True)


TOY_REFERENCE = """\
[toy2020]
authors = "Author T"
title = "Toy cells"
year = 2020
doi = "10.1000/toy"
"""

TOY_CELLS_TEXT = """\
+++
key = "cells-toy"
status = "draft"
+++
## Overview
A toy circuit.

## Cell big
Big cells receive from small cells [toy2020].

## Cell small
Small cells receive the input.

## Cell stop
Stop cells hold big cells back.

## Layer upper
The upper layer holds big cells.

## Layer lower
The lower layer holds small cells.

## Box input
The input arrives here.

## Basic step 1
Basic one

## Basic step 2
Basic two

## Full step 1
Full one

## Full step 2
Full two

## Full step 3
Full three
"""


def toy_cell_view():
    from cns_atlas.cells import (Box, CellStep, CellType, CellView, Flow, Layer, Placement,
                                 Polyline, Reconstruction)

    def shape(n: int) -> Reconstruction:
        return Reconstruction(n, f"toy-{n}", "rat", "Toy", "10.1000/toy", "Author T (2020)", (
            Polyline(((0.0, 0.0, 0.02), (0.0, 0.6, 0.01))),
            Polyline(((0.0, 0.6, 0.01), (-0.2, 1.0, 0.01))),
            Polyline(((0.0, 0.6, 0.01), (0.2, 1.0, 0.01)))))

    layers = (Layer("upper", "Upper layer", "top", (90, 140, 230),
                    ((100.0, 200.0), (500.0, 150.0), (900.0, 200.0)), 40.0),
              Layer("lower", "Lower layer", "bottom", (160, 110, 200),
                    ((100.0, 500.0), (500.0, 550.0), (900.0, 500.0)), 40.0))
    cells = (CellType("big", "Big cell", "basic", 120.0,
                      (Placement("upper", 0.1, 0.9, 3, "lower"),), (shape(1), shape(2))),
             CellType("small", "Small cell", "basic", 60.0,
                      (Placement("lower", 0.1, 0.9, 4, "upper"),), (shape(3),)),
             CellType("stop", "Stop cell", "full", 50.0,
                      (Placement("lower", 0.3, 0.7, 2, "upper"),), (shape(4),)))
    flows = (Flow("f1", "excitatory", "box:input.out", "cell:small", "input path",
                  ((60.0, 640.0), (300.0, 600.0), (400.0, 540.0))),
             Flow("f2", "excitatory", "cell:small", "cell:big", "up path",
                  ((600.0, 520.0), (650.0, 350.0), (600.0, 210.0))),
             Flow("f3", "inhibitory", "cell:stop", "cell:big", "hold back",
                  ((450.0, 520.0), (420.0, 350.0), (450.0, 210.0))))
    basic = (CellStep(("f1",), ("small",)), CellStep(("f2",), ("big",)))
    full = (*basic, CellStep(("f3",), ("big",)))
    return CellView("toy", "Toy cells", (100,), "mid-body", (1000.0, 700.0), layers,
                    (Box("input", "Input", (60.0, 660.0), (100.0, 40.0), {"out": (60.0, 640.0)}),),
                    cells, flows, {"basic": basic, "full": full})
