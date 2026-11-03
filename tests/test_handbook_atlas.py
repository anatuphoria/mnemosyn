from pathlib import Path

import pytest

from cns_atlas import Atlas
from tools.handbook.experiments import AtlasClaim, check_atlas_claim, load

SHAREABLE = Path(__file__).resolve().parents[1] / "build" / "atlas-shareable"


@pytest.fixture(scope="module", params=["local", "shareable"])
def real_atlas(request):
    from cns_desktop.app import default_atlas

    path = default_atlas() if request.param == "local" else SHAREABLE
    if not (path / "metadata.json").exists():
        pytest.skip(f"no {request.param} atlas built")
    return Atlas.open(path)


@pytest.mark.slow
def test_every_handbook_atlas_claim_holds(real_atlas):
    _lab, claims = load()
    assert {c.kind for c in claims} == {"territory", "route"}
    for claim in claims:
        passed, detail = check_atlas_claim(real_atlas, claim)
        assert passed, (claim.slug, detail)


@pytest.mark.slow
def test_atlas_claims_fail_when_they_are_wrong(real_atlas):
    wrong_hit = AtlasClaim("x", "territory", "Middle cerebral artery frontal territory (left)",
                           ("Cuneus (left)",))
    no_cross = AtlasClaim("x", "route", "papez", ("crosses",))
    assert not check_atlas_claim(real_atlas, wrong_hit)[0]
    assert not check_atlas_claim(real_atlas, no_cross)[0]
