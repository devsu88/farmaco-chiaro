from pathlib import Path

from aifa_rag.chunk import (
    build_chunks,
    document_rows,
    iter_units,
    merge_units,
    recursive_split,
)

FIX = Path(__file__).parent / "fixtures" / "sample.md"


def test_short_subsections_are_not_merged_across_keys():
    chunks = build_chunks(FIX)
    non_prenda = [c for c in chunks if c.sottosezione_key == "non_prenda"]
    avvertenze = [c for c in chunks if c.sottosezione_key == "avvertenze"]
    assert non_prenda and avvertenze
    assert all("Avvertenze e precauzioni" not in c.testo for c in non_prenda)


def test_merge_same_subsection_up_to_target():
    units = iter_units("Paragrafo uno. " * 50 + "\n\n" + "Paragrafo due. " * 50)
    groups = merge_units(units, max_tokens=600)
    assert len(groups) >= 1
    assert all(sum(len(u.text) for u in g) // 4 <= 600 for g in groups)


def test_oversized_section_is_split_with_overlap():
    text = "Frase di prova. " * 400
    parts = recursive_split(text, max_tokens=600, overlap=80)
    assert len(parts) > 1
    assert all(len(p) // 4 <= 800 for p in parts)


def test_bullets_are_atomic():
    chunks = build_chunks(FIX)
    for chunk in chunks:
        for line in chunk.testo.splitlines():
            if line.startswith("- "):
                assert len(line) > 2


def test_chunk_metadata_and_parent():
    chunks = build_chunks(FIX)
    assert all(c.parent_id for c in chunks)
    assert all(c.heading_path.count(">") == 2 for c in chunks)
    assert all(c.pagina >= 1 for c in chunks)
    assert all(c.farmaco_id == "012745_sample" for c in chunks)
    assert all(c.blocco_id.startswith("012745_sample_") for c in chunks)
    assert all(c.parent_id.startswith("012745_sample_") for c in chunks)


def test_blocco_ids_match_document_blocks():
    chunks = build_chunks(FIX)
    document = document_rows(FIX)
    blocchi = {row["blocco_id"] for row in document}
    assert {chunk.blocco_id for chunk in chunks} <= blocchi


def test_chunk_text_is_inside_its_document_block():
    chunks = build_chunks(FIX)
    document = {row["blocco_id"]: row["testo"] for row in document_rows(FIX)}
    for chunk in chunks:
        assert chunk.testo in document[chunk.blocco_id]


def test_min_chars_filtered():
    chunks = build_chunks(FIX)
    assert all(len(c.testo.strip()) >= 40 for c in chunks)


def test_chunk_ids_are_unique_when_subsections_repeat(tmp_path):
    md = tmp_path / "01.md"
    md.write_text(
        "---\ndrug_id: \"004763\"\nnome: \"ASPIRINA\"\n---\n\n"
        "# ASPIRINA 500 mg\n\n"
        "## 2. Cosa deve sapere prima di prendere Aspirina\n\n"
        "### Gravidanza – ultimo trimestre\n\n"
        "Non prenda Aspirina negli ultimi tre mesi di gravidanza.\n\n"
        "### Gravidanza - primo e secondo trimestre\n\n"
        "Non dovrebbe assumere Aspirina nei primi sei mesi di gravidanza.\n",
        encoding="utf-8",
    )
    chunks = build_chunks(md)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert {c.sottosezione_key for c in chunks} == {"gravidanza"}
