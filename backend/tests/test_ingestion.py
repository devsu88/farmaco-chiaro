from scripts.ingest_vector_index import build_records, chunk_text


def test_chunk_text_crea_chunk_brevi():
    testo = "Frase di prova. " * 300
    chunks = chunk_text(testo, max_chars=500, overlap=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)


def test_build_records_contiene_metadata_blocco():
    records = build_records(max_chars=1200, overlap=150, farmaco_filtro="plasil")
    assert records
    primo = records[0]
    assert primo["metadata"]["farmaco_id"] == "plasil"
    assert primo["metadata"]["blocco_id"].startswith("plasil_")
    assert primo["testo"].strip()
