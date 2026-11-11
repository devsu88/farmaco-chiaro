"""I blocchi del documento hanno titolo, testo e id stabili."""
from __future__ import annotations

import re

from services.retrieval import blocchi_per_farmaco

FARMACI = ["012745_01", "004763_01", "026089_01", "025669_01", "020766_02"]
ID_RE = re.compile(r"^(?P<farmaco>.+)_(?P<sezione>\d+)_(?P<indice>\d{2})$")


def test_ogni_blocco_ha_titolo_e_testo():
    for farmaco_id in FARMACI:
        blocchi = blocchi_per_farmaco(farmaco_id)
        assert blocchi, farmaco_id
        for blocco in blocchi:
            assert blocco["sezione"].strip()
            assert blocco["paragrafo"].strip()
            assert blocco["testo"].strip()


def test_id_dei_blocchi_sono_univoci_e_nel_formato_atteso():
    for farmaco_id in FARMACI:
        ids = [blocco["blocco_id"] for blocco in blocchi_per_farmaco(farmaco_id)]
        assert len(ids) == len(set(ids))
        for blocco_id in ids:
            trovato = ID_RE.match(blocco_id)
            assert trovato, blocco_id
            assert trovato.group("farmaco") == farmaco_id


def test_il_titolo_del_paragrafo_e_metadato_del_blocco():
    blocchi = {
        blocco["blocco_id"]: blocco for blocco in blocchi_per_farmaco("020766_02")
    }
    blocco = blocchi["020766_02_3_02"]
    assert blocco["paragrafo"] == "Se dimentica di prendere Plasil"
    assert "non prenda una dose doppia" in blocco["testo"].lower()


def test_il_documento_parte_dalla_sezione_1():
    blocchi = blocchi_per_farmaco("012745_01")
    assert blocchi[0]["blocco_id"] == "012745_01_1_00"
    assert blocchi[0]["sezione_num"] == 1
