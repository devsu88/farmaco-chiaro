from app import farmaci


def test_registro_completo():
    assert {f.id for f in farmaci.all()} == {
        "tachipirina_1000",
        "aspirina_500",
        "augmentin",
        "moment",
        "plasil",
    }


def test_file_markdown_esistono():
    assert farmaci.valida_file() == []


def test_tachipirina_file_corretto():
    farmaco = farmaci.require("tachipirina_1000")
    assert farmaco.path_fi.name == "TACHIPIRINA_FI.md"
    assert farmaco.path_fi.exists()
    assert farmaco.path_rcp.exists()
