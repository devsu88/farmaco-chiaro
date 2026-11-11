"""Chunking ibrido dei fogli illustrativi: prima la struttura, poi i token."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from aifa_rag import config
from aifa_rag.markdown import SUBSECTION_PATTERNS

PAGE_RE = re.compile(r"^<!--\s*page:\s*(\d+)\s*-->$")
H1_RE = re.compile(r"^#\s+(.*)$")
H2_RE = re.compile(r"^##\s+(\d)\.\s*(.*)$")
H3_RE = re.compile(r"^###\s+(.*)$")

SECTION_KEYS = {
    1: "indicazioni",
    2: "avvertenze_e_controindicazioni",
    3: "posologia",
    4: "effetti_indesiderati",
    5: "conservazione",
    6: "composizione",
}


@dataclass
class Unit:
    kind: str  # paragraph | bullet | table
    text: str
    page: int


@dataclass
class Chunk:
    chunk_id: str
    farmaco_id: str
    drug_id: str
    nome: str
    principi_attivi: list[str]
    atc: str
    tipo: str
    foglio: str
    sezione_num: int
    sezione_key: str
    sezione_titolo: str
    sottosezione_key: str
    sottosezione_titolo: str
    heading_path: str
    parent_id: str
    blocco_id: str
    testo: str
    pagina: int
    source_url: str
    n_tokens: int


def estimate_tokens(text: str) -> int:
    """Stima grezza: ~4 caratteri per token (documentato, non esatto)."""
    return max(1, len(text) // 4)


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:60]


def _sub_key(title: str, sezione_num: int) -> str:
    for key, pattern in SUBSECTION_PATTERNS.get(sezione_num, []):
        if pattern.match(title):
            return key
    return _slug(title) or "body"


def _front_matter(lines: list[str]) -> tuple[dict, int]:
    if not lines or lines[0].strip() != "---":
        return {}, 0
    meta: dict = {}
    for idx in range(1, len(lines)):
        line = lines[idx]
        if line.strip() == "---":
            return meta, idx + 1
        if ":" in line:
            key, _, raw = line.partition(":")
            raw = raw.strip()
            try:
                meta[key.strip()] = json.loads(raw)
            except json.JSONDecodeError:
                meta[key.strip()] = raw.strip('"')
    return meta, 0


def _flush_block(current: tuple[str, list[str], int] | None, units: list[Unit]) -> None:
    if current is None:
        return
    kind, lines, page = current
    if kind == "bullet":
        units.extend(Unit("bullet", line.strip(), page) for line in lines if line.strip())
    elif kind == "table":
        units.append(Unit("table", "\n".join(line.rstrip() for line in lines), page))
    else:
        text = " ".join(line.strip() for line in lines).strip()
        if text:
            units.append(Unit("paragraph", text, page))


def iter_units(section_text: str, page: int = 1) -> list[Unit]:
    """Converte un blocco Markdown in unità atomiche (paragrafi, bullet, tabelle)."""
    units: list[Unit] = []
    current: tuple[str, list[str], int] | None = None

    for line in section_text.splitlines():
        if not line.strip():
            _flush_block(current, units)
            current = None
            continue
        if line.startswith("|"):
            kind = "table"
        elif line.startswith("- "):
            kind = "bullet"
        else:
            kind = "paragraph"
        if current is None or current[0] != kind:
            _flush_block(current, units)
            current = (kind, [line], page)
        else:
            current[1].append(line)

    _flush_block(current, units)
    return units


def merge_units(units: list[Unit], max_tokens: int = config.CHUNK_TARGET_TOKENS) -> list[list[Unit]]:
    """Accorpa unità adiacenti senza mai superare ``max_tokens``."""
    groups: list[list[Unit]] = []
    current: list[Unit] = []
    current_tokens = 0

    for unit in units:
        tokens = estimate_tokens(unit.text)
        if current and current_tokens + tokens > max_tokens:
            groups.append(current)
            current, current_tokens = [], 0
        current.append(unit)
        current_tokens += tokens

    if current:
        groups.append(current)
    return groups


def _hard_split(text: str, max_chars: int) -> list[str]:
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def recursive_split(
    text: str,
    max_tokens: int = config.CHUNK_TARGET_TOKENS,
    overlap: int = config.CHUNK_OVERLAP_TOKENS,
) -> list[str]:
    """Ultima risorsa: spezza un paragrafo troppo lungo, con overlap."""
    max_chars = max_tokens * 4
    overlap_chars = overlap * 4
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    parts: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                parts.append(current.strip())
                current = ""
            pieces = _hard_split(sentence, max_chars)
            parts.extend(pieces[:-1])
            current = pieces[-1]
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > max_chars:
            parts.append(current.strip())
            tail = current[-overlap_chars:] if overlap_chars else ""
            current = f"{tail} {sentence}".strip() if tail else sentence
            if len(current) > max_chars:
                pieces = _hard_split(current, max_chars)
                parts.extend(pieces[:-1])
                current = pieces[-1]
        else:
            current = candidate

    if current.strip():
        parts.append(current.strip())
    return parts


def contextualize(nome: str, foglio: str, sezione: str, sottosezione: str, text: str) -> str:
    """Header contestuale anteposto al testo per l'embedding (non per la citazione)."""
    header = " — ".join(part for part in (nome, foglio, sezione, sottosezione) if part)
    return f"{header}\n{text}"


def parse_markdown(md_text: str) -> dict:
    """Costruisce l'albero H1 → H2 → H3 con le unità di testo."""
    lines = md_text.splitlines()
    meta, start = _front_matter(lines)

    foglio = ""
    sections: list[dict] = []
    section: dict | None = None
    subsection: dict | None = None
    page = 1
    current: tuple[str, list[str], int] | None = None

    def units_for() -> list[Unit]:
        nonlocal subsection
        if subsection is None:
            subsection = {
                "key": "body",
                "titolo": section["titolo"] if section else "",
                "units": [],
            }
            if section is not None:
                section["subs"].append(subsection)
        return subsection["units"]

    def flush() -> None:
        nonlocal current
        _flush_block(current, units_for())
        current = None

    for line in lines[start:]:
        stripped = line.strip()
        marker = PAGE_RE.match(stripped)
        if marker:
            flush()
            page = int(marker.group(1))
            continue
        if not stripped:
            flush()
            continue
        if line.startswith("# "):
            flush()
            foglio = H1_RE.match(line).group(1).strip()
            continue
        heading2 = H2_RE.match(line)
        if heading2:
            flush()
            section = {
                "num": int(heading2.group(1)),
                "titolo": heading2.group(2).strip(),
                "subs": [],
            }
            sections.append(section)
            subsection = None
            continue
        heading3 = H3_RE.match(line)
        if heading3:
            flush()
            title = heading3.group(1).strip()
            subsection = {
                "key": _sub_key(title, section["num"] if section else 0),
                "titolo": title,
                "units": [],
            }
            if section is not None:
                section["subs"].append(subsection)
            continue

        if line.startswith("|"):
            kind = "table"
        elif line.startswith("- "):
            kind = "bullet"
        else:
            kind = "paragraph"
        if current is None or current[0] != kind:
            flush()
            current = (kind, [line], page)
        else:
            current[1].append(line)

    flush()
    return {"meta": meta, "foglio": foglio, "sections": sections}


def build_chunks(md_path: Path) -> list[Chunk]:
    doc = parse_markdown(md_path.read_text(encoding="utf-8"))
    meta = doc["meta"]
    foglio = doc["foglio"] or meta.get("foglio", "")
    leaflet_index = md_path.stem
    drug_id = str(meta.get("drug_id", ""))
    farmaco_id = f"{drug_id}_{leaflet_index}"

    chunks: list[Chunk] = []
    for section in doc["sections"]:
        number = section["num"]
        section_key = SECTION_KEYS.get(number, f"sezione_{number}")
        parent_id = f"{farmaco_id}_{number}"
        for sub_index, subsection in enumerate(section["subs"]):
            blocco_id = f"{farmaco_id}_{number}_{sub_index:02d}"
            groups = merge_units(subsection["units"], config.CHUNK_TARGET_TOKENS)
            for group_index, group in enumerate(groups):
                text = "\n\n".join(unit.text for unit in group).strip()
                if len(text) < config.CHUNK_MIN_CHARS:
                    continue
                atomic = len(group) == 1 and group[0].kind != "paragraph"
                if estimate_tokens(text) > config.CHUNK_MAX_TOKENS and not atomic:
                    parts = recursive_split(
                        text,
                        config.CHUNK_TARGET_TOKENS,
                        config.CHUNK_OVERLAP_TOKENS,
                    )
                else:
                    parts = [text]

                for part_index, part in enumerate(parts):
                    chunks.append(
                        Chunk(
                            chunk_id=(
                                f"{drug_id}_{leaflet_index}_{number}_{sub_index:02d}_"
                                f"{subsection['key']}_{group_index:02d}_{part_index:02d}"
                            ),
                            farmaco_id=farmaco_id,
                            drug_id=drug_id,
                            nome=str(meta.get("nome", "")),
                            principi_attivi=list(meta.get("principi_attivi", [])),
                            atc=str(meta.get("atc", "")),
                            tipo="FI",
                            foglio=foglio,
                            sezione_num=number,
                            sezione_key=section_key,
                            sezione_titolo=section["titolo"],
                            sottosezione_key=subsection["key"],
                            sottosezione_titolo=subsection["titolo"],
                            heading_path=f"{foglio} > {section['titolo']} > {subsection['titolo']}",
                            parent_id=parent_id,
                            blocco_id=blocco_id,
                            testo=part,
                            pagina=group[0].page,
                            source_url=str(meta.get("source_url", "")),
                            n_tokens=estimate_tokens(part),
                        )
                    )
    return chunks


def section_rows(md_path: Path) -> list[dict]:
    """Estrae le sezioni H2 intere, per l'espansione small-to-big."""
    doc = parse_markdown(md_path.read_text(encoding="utf-8"))
    meta = doc["meta"]
    foglio = doc["foglio"] or meta.get("foglio", "")
    drug_id = str(meta.get("drug_id", ""))
    leaflet_index = md_path.stem
    farmaco_id = f"{drug_id}_{leaflet_index}"

    rows: list[dict] = []
    for section in doc["sections"]:
        testo = "\n\n".join(
            unit.text for subsection in section["subs"] for unit in subsection["units"]
        ).strip()
        if not testo:
            continue
        number = section["num"]
        rows.append(
            {
                "parent_id": f"{farmaco_id}_{number}",
                "farmaco_id": farmaco_id,
                "drug_id": drug_id,
                "foglio": foglio,
                "sezione_num": number,
                "sezione_key": SECTION_KEYS.get(number, f"sezione_{number}"),
                "sezione_titolo": section["titolo"],
                "testo": testo,
                "source_url": str(meta.get("source_url", "")),
            }
        )
    return rows


def document_rows(md_path: Path) -> list[dict]:
    """Blocchi H3/H2 mostrati nel pannello "documento originale".

    Il ``blocco_id`` è lo stesso assegnato ai chunk: una citazione del
    retrieval può quindi evidenziare il blocco giusto senza offset fragili.
    """
    md_text = md_path.read_text(encoding="utf-8")
    doc = parse_markdown(md_text)
    meta = doc["meta"]
    foglio = doc["foglio"] or meta.get("foglio", "")
    drug_id = str(meta.get("drug_id", ""))
    leaflet_index = md_path.stem
    farmaco_id = f"{drug_id}_{leaflet_index}"
    documento = f"Foglio illustrativo {foglio}".strip()

    rows: list[dict] = []
    for section in doc["sections"]:
        number = section["num"]
        section_key = SECTION_KEYS.get(number, f"sezione_{number}")
        for sub_index, subsection in enumerate(section["subs"]):
            testo = "\n\n".join(unit.text for unit in subsection["units"]).strip()
            if len(testo) < config.CHUNK_MIN_CHARS:
                continue
            rows.append(
                {
                    "blocco_id": f"{farmaco_id}_{number}_{sub_index:02d}",
                    "farmaco_id": farmaco_id,
                    "drug_id": drug_id,
                    "leaflet": leaflet_index,
                    "documento": documento,
                    "sezione": section["titolo"],
                    "sezione_num": number,
                    "sezione_key": section_key,
                    "paragrafo": subsection["titolo"],
                    "sottosezione_key": subsection["key"],
                    "testo": testo,
                    "pagina": subsection["units"][0].page if subsection["units"] else 1,
                }
            )
    return rows


def write_chunks(chunks: Iterable[Chunk], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    count = 0
    with tmp.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
            count += 1
    tmp.replace(path)
    return count
