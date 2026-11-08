"""I titoli dei paragrafi fanno parte del contenuto citabile."""
from __future__ import annotations

from services.retrieval import blocchi_per_farmaco


def test_il_titolo_del_paragrafo_e_nel_testo_del_blocco():
    blocchi = {blocco["id"]: blocco for blocco in blocchi_per_farmaco("plasil")}
    assert "Non prenda una dose doppia" in blocchi["plasil_sec13"]["testo"]


def test_il_titolo_non_viene_duplicato():
    blocchi = {blocco["id"]: blocco for blocco in blocchi_per_farmaco("augmentin")}
    testo = blocchi["augmentin_sec10"]["testo"]
    assert testo.lower().count("se dimentica di prendere una dose") == 1


def test_numero_e_id_dei_blocchi_restano_stabili():
    from services.retrieval import _load_blocchi

    blocchi = _load_blocchi()
    assert len(blocchi) == 91
    ids = {blocco["id"] for blocco in blocchi}
    for blocco_id in ("plasil_sec13", "augmentin_sec10", "tachipirina_1000_sec9"):
        assert blocco_id in ids
