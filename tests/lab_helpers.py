from pathlib import Path

from atlas_fixtures import TOY_LAB_TEXTS, TOY_MODEL, TOY_REFERENCES
from cns_atlas.knowledge import load_references

TOY_IDS = {1, 2, 100, 101, 102, 110, 111, 112, 120}


def write_toy_model(root: Path, model: str = TOY_MODEL, texts: str = TOY_LAB_TEXTS) -> Path:
    (root / "models").mkdir(parents=True, exist_ok=True)
    (root / "knowledge" / "en").mkdir(parents=True, exist_ok=True)
    (root / "models" / "toy.toml").write_text(model)
    (root / "knowledge" / "en" / "lab-toy.toml").write_text(texts)
    (root / "knowledge" / "references.toml").write_text(TOY_REFERENCES)
    return root


def load_toy(root: Path, model: str = TOY_MODEL, texts: str = TOY_LAB_TEXTS):
    from tools.build_atlas.models import load_models

    write_toy_model(root, model, texts)
    references = load_references(root / "knowledge" / "references.toml")
    return load_models(root / "models", root / "knowledge", TOY_IDS, references, {"mood"})


def toy_model(root: Path):
    return load_toy(root)[0]
