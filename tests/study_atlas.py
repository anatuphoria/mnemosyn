from pathlib import Path

from atlas_package import tetra, write_package
from cns_atlas import Atlas, Structure

GREY = (170, 170, 180)


def _s(sid, acronym, name, path, kind="region", side="none", concept=None, synonyms=()):
    return Structure(sid, acronym, name, path, GREY, kind=kind, side=side, concept=concept,
                     synonyms=synonyms)


def _group(sid, acronym, name, path):
    return _s(sid, acronym, name, path, kind="group")


def _pair(sid, acronym, name, path, kind="region", synonyms=()):
    return [_s(sid, acronym, name, path, kind, synonyms=synonyms),
            _s(sid + 1, f"{acronym}-L", f"{name} (left)", (*path, sid + 1), kind, "left", sid),
            _s(sid + 2, f"{acronym}-R", f"{name} (right)", (*path, sid + 2), kind, "right", sid)]


def study_structures() -> list[Structure]:
    return [
        _group(1, "CNS", "Central nervous system", (1,)),
        _group(2, "Br", "Brain", (1, 2)),
        _group(10, "FL", "Frontal lobe", (1, 2, 10)),
        *_pair(100, "PreCG", "Precentral gyrus", (1, 2, 10, 100), synonyms=("motor strip",)),
        *_pair(110, "MFG", "Middle frontal gyrus", (1, 2, 10, 110)),
        *_pair(120, "IFGoperc", "Inferior frontal gyrus, opercular part", (1, 2, 10, 120)),
        _group(20, "TL", "Temporal lobe", (1, 2, 20)),
        *_pair(200, "MTG", "Middle temporal gyrus", (1, 2, 20, 200)),
        *_pair(210, "STG", "Superior temporal gyrus", (1, 2, 20, 210)),
        _group(30, "DI", "Diencephalon", (1, 2, 30)),
        _group(31, "TH", "Thalamus", (1, 2, 30, 31)),
        *_pair(300, "LGN", "Lateral geniculate nucleus", (1, 2, 30, 31, 300), "nucleus"),
        *_pair(310, "MGN", "Medial geniculate nucleus", (1, 2, 30, 31, 310), "nucleus"),
        _group(40, "BS", "Brainstem", (1, 2, 40)),
        _group(41, "P", "Pons", (1, 2, 40, 41)),
        *_pair(400, "LC", "Locus coeruleus", (1, 2, 40, 41, 400), "nucleus"),
        _s(410, "DR", "Dorsal raphe nucleus", (1, 2, 40, 410), "nucleus", "midline"),
        _group(60, "VERM", "Vermis", (1, 2, 60)),
        _s(600, "VerVII", "Vermis lobule VII", (1, 2, 60, 600), side="midline"),
        _s(610, "VerVIII", "Vermis lobule VIII", (1, 2, 60, 610), side="midline"),
        _group(50, "EMP", "Empty group", (1, 2, 50)),
        _s(500, "NOM", "No mesh structure", (1, 2, 50, 500)),
    ]


def study_atlas(root: Path, entries: dict[int, str] | None = None) -> Atlas:
    structures = study_structures()
    meshes = {s.id: tetra(float(n)) for n, s in enumerate(structures) if s.side != "none"}
    package = write_package(root / "pkg", structures, meshes=meshes,
                            entries={"en": entries or {}})
    return Atlas.open(package)


def entry(structure_id: int, status: str) -> str:
    return f'+++\nid = {structure_id}\nstatus = "{status}"\n+++\n## Function\nTest text.\n'
