from app import farmaci

ATTESI = {
    "012745_01",
    "004763_01",
    "026089_01",
    "025669_01",
    "020766_02",
}


def test_registro_completo():
    ids = {f.id for f in farmaci.all()}
    assert len(ids) == 621
    assert ATTESI <= ids


def test_artefatti_esistenti():
    assert farmaci.valida_file() == []


def test_mapping_foglio():
    farmaco = farmaci.require("012745_01")
    assert farmaco.drug_id == "012745"
    assert farmaco.leaflet == "01"
    assert farmaco.n_chunks > 0
    assert farmaco.nome == "TACHIPIRINA 1000 mg compresse"
    assert "PARACETAMOLO" in farmaco.principi_attivi


def test_farmaco_inesistente():
    assert farmaci.get("farmaco_inesistente") is None
