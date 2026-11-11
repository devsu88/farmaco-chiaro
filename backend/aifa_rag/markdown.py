"""Converte il testo estratto dai FI AIFA in Markdown strutturato.

Un file Markdown per foglio illustrativo: H1 = foglio, H2 = sezioni 1..6,
H3 = sottosezioni, ``<!-- page: N -->`` per la citazione, front matter YAML.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

LEAFLET_HEADER = re.compile(r"Foglio illustrativo\s*:?\s*informazioni per", re.IGNORECASE)
TOC_HEADER = re.compile(r"Contenuto di questo foglio\s*:?\s*$", re.IGNORECASE)
SECTION_LINE = re.compile(r"^\s*([1-6])\s*[.·]\s*(\S.*?)\s*$", re.MULTILINE)
PAGE_MARKER = "\x00"
WATERMARK = {"aco", "rm", "fa", "ita", "enz", "del", "ag", "lia", "na", "pag"}
FOOTER_PREFIXES = ("Documento reso disponibile da AIFA", "Esula dalla competenza")
PAGE_NUMBER = re.compile(r"^pag\.?\s*\d+$|^\d{1,3}$", re.IGNORECASE)
TRAILING_WATERMARK = re.compile(
    r"\s{2,}(aco|rm|fa|ita|enz|del|ag|lia|na|ia|pag)\s*$", re.IGNORECASE
)

DISCLAIMER_FRAGMENTS = [
    re.compile(r"Documento\s*reso", re.IGNORECASE),
    re.compile(r"disponibil[ei]\s*da\s*AIFA(?:\s*il\s+\d{2}/\d{2}/\d{4})?", re.IGNORECASE),
    re.compile(r"Esula dalla competenza dell[’']AIFA.{0,200}?all[’']AIC dei", re.IGNORECASE),
    re.compile(
        r"medicinali e, pertanto, l[’']Agenzia non può essere ritenuta responsabile.{0,200}?dell[’']autorizzazione",
        re.IGNORECASE,
    ),
    re.compile(r"all[’']immissione in commercio \(o titolare AIC\)\.?", re.IGNORECASE),
]
DISCLAIMER_SIGNATURE = re.compile(
    r"Agenzia non può|titolare AIC|Documento reso disponibile", re.IGNORECASE
)

DEFAULT_TITLES = {
    1: "Che cos'è e a cosa serve",
    2: "Cosa deve sapere prima di prendere",
    3: "Come prendere",
    4: "Possibili effetti indesiderati",
    5: "Come conservare",
    6: "Contenuto della confezione e altre informazioni",
}

SUBSECTION_PATTERNS: dict[int, list[tuple[str, re.Pattern]]] = {
    2: [
        ("non_prenda", re.compile(r"^Non (prenda|usi|dia|faccia prendere)\b", re.IGNORECASE)),
        ("avvertenze", re.compile(r"^Avv[ée]rtenze e precauzioni\b", re.IGNORECASE)),
        ("durante_trattamento", re.compile(r"^Durante il trattamento\b", re.IGNORECASE)),
        ("dosi_elevate", re.compile(r"^Uso di dosi elevate\b", re.IGNORECASE)),
        ("bambini", re.compile(r"^Bambini e adolescenti\b", re.IGNORECASE)),
        ("altri_medicinali", re.compile(r"^Altri medicinali\b", re.IGNORECASE)),
        ("gravidanza", re.compile(r"^Gravidanza\b", re.IGNORECASE)),
        ("allattamento", re.compile(r"^Allattamento\b", re.IGNORECASE)),
        ("guida", re.compile(r"^(Effetti sulla guida|Guida di veicoli)\b", re.IGNORECASE)),
        (
            "eccipienti",
            re.compile(
                r"^.{0,60}\bcontiene (sodio|lattosio|etanolo|zucchero|aspartame|saccarosio)\b",
                re.IGNORECASE,
            ),
        ),
    ],
    3: [
        ("come_prendere", re.compile(r"^Come (prendere|usare)\b", re.IGNORECASE)),
        ("sovradosaggio", re.compile(r"^Se (prende|usa) più\b", re.IGNORECASE)),
        ("dimenticanza", re.compile(r"^Se dimentica\b", re.IGNORECASE)),
        ("interruzione", re.compile(r"^Se interrompe\b", re.IGNORECASE)),
    ],
    4: [
        ("segnalazione", re.compile(r"^(Segnalazione|Come segnalare)\b", re.IGNORECASE)),
        ("frequenza", re.compile(r"^Frequenza\b", re.IGNORECASE)),
    ],
    5: [("conservazione", re.compile(r"^(Conservazione|Come conservare)\b", re.IGNORECASE))],
    6: [
        ("composizione", re.compile(r"^Cosa contiene\b", re.IGNORECASE)),
        ("descrizione", re.compile(r"^Descrizione dell.aspetto\b", re.IGNORECASE)),
        ("titolare", re.compile(r"^Titolare dell.autorizzazione\b", re.IGNORECASE)),
        ("produttore", re.compile(r"^Produttor[ei]\b", re.IGNORECASE)),
        ("aggiornamento", re.compile(r"^Questo foglio illustrativo\b", re.IGNORECASE)),
    ],
}


@dataclass
class Subsection:
    key: str
    title: str
    text: str


@dataclass
class LeafletText:
    titolo: str
    forme: list[str]
    pages: list[str]
    page_numbers: list[int]

    @property
    def body(self) -> str:
        return "\n".join(
            f"{page}\n{PAGE_MARKER}{number}\n"
            for page, number in zip(self.pages, self.page_numbers)
        )


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text)


def _title_from_page(page: str) -> str:
    lines = page.splitlines()
    for idx, line in enumerate(lines):
        if LEAFLET_HEADER.search(line):
            for candidate in lines[idx + 1 : idx + 8]:
                text = candidate.strip()
                if text and text.lower() not in WATERMARK and len(text) > 3:
                    return text
    return ""


def split_leaflets(pages: list[str]) -> list[LeafletText]:
    """Separa le pagine di un PDF nei singoli fogli illustrativi concatenati."""
    groups: list[tuple[list[str], list[int]]] = []
    current: list[str] = []
    numbers: list[int] = []

    for number, page in enumerate(pages, start=1):
        if LEAFLET_HEADER.search(page[:500]) and current:
            groups.append((current, numbers))
            current, numbers = [], []
        current.append(page)
        numbers.append(number)
    if current:
        groups.append((current, numbers))

    leaflets = []
    for group_pages, group_numbers in groups:
        titolo = _title_from_page(group_pages[0])
        leaflets.append(
            LeafletText(
                titolo=titolo,
                forme=[titolo] if titolo else [],
                pages=group_pages,
                page_numbers=group_numbers,
            )
        )
    return leaflets


def parse_toc(text: str) -> dict[int, str]:
    """Estrae i titoli delle 6 sezioni dal sommario del foglio."""
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if TOC_HEADER.search(line.strip()):
            start = idx + 1
            break
    if start is None:
        return {}

    toc: dict[int, str] = {}
    pending: int | None = None
    for line in lines[start : start + 40]:
        stripped = line.strip()
        if not stripped:
            continue
        match = SECTION_LINE.match(stripped)
        if match:
            number, title = int(match.group(1)), match.group(2).strip()
            if number in toc:
                break
            if title:
                toc[number] = title
                pending = None
            else:
                pending = number
            continue
        if pending is not None:
            toc[pending] = stripped
            pending = None
            continue
        if toc:
            break
    return toc


def _section_candidates(text: str) -> list[tuple[int, str, int, int]]:
    """Ritorna (numero, titolo, inizio corpo, fine corpo) per ogni heading."""
    matches = [(int(m.group(1)), m.group(2).strip(), m.start(), m.end()) for m in SECTION_LINE.finditer(text)]
    candidates = []
    for idx, (number, title, _start, end) in enumerate(matches):
        body_end = matches[idx + 1][2] if idx + 1 < len(matches) else len(text)
        candidates.append((number, title, end, body_end))
    return candidates


def split_sections(text: str, toc: dict[int, str] | None = None) -> dict[int, str]:
    """Divide il testo nelle sezioni 1..6, scegliendo il blocco più sostanzioso."""
    toc = toc or {}
    candidates = _section_candidates(text)
    sections: dict[int, str] = {}

    for number in range(1, 7):
        expected = _norm(toc.get(number, ""))
        best: tuple[int, str] | None = None
        for cand_number, title, start, end in candidates:
            if cand_number != number:
                continue
            if expected:
                actual = _norm(title)
                ratio = SequenceMatcher(None, expected, actual).ratio()
                if not (ratio > 0.72 or actual.startswith(expected[:20]) or expected.startswith(actual[:20])):
                    continue
            body = text[start:end]
            if best is None or len(body) > len(best[1]):
                best = (start, body)
        if best is not None:
            sections[number] = best[1]
    return sections


def detect_subsections(section_text: str, sezione_num: int) -> list[Subsection]:
    """Individua le sottosezioni note dentro una sezione."""
    patterns = SUBSECTION_PATTERNS.get(sezione_num, [])
    if not patterns or not section_text.strip():
        return [Subsection("body", "", section_text)] if section_text.strip() else []

    lines = section_text.splitlines()
    hits: list[tuple[int, str, str]] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 90:
            continue
        if stripped.endswith((",", ";", "(", "“", "«")):
            continue
        for key, pattern in patterns:
            if pattern.match(stripped):
                hits.append((idx, key, _strip_watermark(stripped)))
                break

    if not hits:
        return [Subsection("body", "", section_text)]

    subsections: list[Subsection] = []
    first = hits[0][0]
    intro = "\n".join(lines[:first]).strip()
    if intro:
        subsections.append(Subsection("intro", "", intro))

    for pos, (idx, key, title) in enumerate(hits):
        end = hits[pos + 1][0] if pos + 1 < len(hits) else len(lines)
        body = "\n".join(lines[idx + 1 : end]).strip()
        subsections.append(Subsection(key, title, body))
    return subsections


def _strip_watermark(text: str) -> str:
    return TRAILING_WATERMARK.sub("", text).strip()


def _clean_line(line: str) -> str | None:
    stripped = line.rstrip()
    text = stripped.strip()
    if not text:
        return ""
    for pattern in DISCLAIMER_FRAGMENTS:
        stripped = pattern.sub("", stripped)
    stripped = TRAILING_WATERMARK.sub("", stripped)
    text = stripped.strip()
    if not text:
        return None
    if DISCLAIMER_SIGNATURE.search(text):
        return None
    if re.search(r"AIFA\s*il\s*\d{2}/\d{2}/\d{4}|all[’']AIC\s+di\s+\d+", text, re.IGNORECASE):
        return None
    if text.lower() in WATERMARK:
        return None
    if len(text) <= 3 and text.isalpha() and text.islower():
        return None
    if text.startswith(FOOTER_PREFIXES):
        return None
    if PAGE_NUMBER.match(text):
        return None
    return stripped


def _is_table_row(line: str) -> bool:
    cells = re.split(r"\s{2,}", line.strip())
    return len(cells) >= 3


def _split_cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"\s{2,}", line.strip()) if cell.strip()]


def _render_table(rows: list[str]) -> list[str]:
    cells = [_split_cells(row) for row in rows]
    widths = {len(row) for row in cells}
    if len(widths) != 1 or len(cells[0]) < 2:
        block = ["<!-- table: uncertain -->", "```text", *rows, "```"]
        return block

    out = ["| " + " | ".join(cells[0]) + " |"]
    out.append("| " + " | ".join("---" for _ in cells[0]) + " |")
    for row in cells[1:]:
        out.append("| " + " | ".join(row) + " |")
    return out


def render_blocks(text: str) -> list[str]:
    """Converte un blocco di testo in paragrafi, bullet, tabelle e marker pagina."""
    out: list[str] = []
    paragraph: list[str] = []
    bullet: list[str] | None = None
    table: list[str] = []
    skip_footer = 0

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            out.append(" ".join(part.strip() for part in paragraph))
            out.append("")
            paragraph = []

    def flush_bullet() -> None:
        nonlocal bullet
        if bullet is not None:
            out.append("- " + " ".join(part.strip() for part in bullet))
            bullet = None

    def flush_table() -> None:
        nonlocal table
        if table:
            if len(table) >= 2:
                out.extend(_render_table(table))
            else:
                out.append(table[0].strip())
            out.append("")
            table = []

    for raw in text.splitlines():
        if raw.startswith(PAGE_MARKER):
            flush_paragraph()
            flush_bullet()
            flush_table()
            out.append(f"<!-- page: {raw[len(PAGE_MARKER):].strip()} -->")
            out.append("")
            continue

        if skip_footer:
            if raw.strip():
                skip_footer -= 1
                continue
            skip_footer = 0
        if raw.strip().startswith("Documento reso disponibile da AIFA"):
            skip_footer = 4
            continue

        line = _clean_line(raw)
        if line is None:
            continue
        if not line.strip():
            flush_paragraph()
            flush_bullet()
            flush_table()
            continue

        stripped = line.strip()
        if _is_table_row(line):
            flush_paragraph()
            flush_bullet()
            table.append(stripped)
            continue
        flush_table()

        if stripped.startswith(("- ", "• ", "– ")):
            flush_paragraph()
            flush_bullet()
            bullet = [stripped[2:].strip()]
            continue

        if bullet is not None:
            indent = len(line) - len(line.lstrip())
            if indent >= 2 and not stripped[0].isupper():
                bullet.append(stripped)
                continue
            flush_bullet()

        paragraph.append(stripped)

    flush_paragraph()
    flush_bullet()
    flush_table()
    return out


def _front_matter(meta: dict, leaflet: LeafletText, source_url: str, fetched_at: str) -> str:
    fields = {
        "drug_id": meta.get("drug_id", ""),
        "aic": meta.get("aic", ""),
        "nome": meta.get("nome", ""),
        "principi_attivi": meta.get("principi_attivi", []),
        "atc": meta.get("atc", ""),
        "ditta": meta.get("ditta", ""),
        "forma": meta.get("forma", ""),
        "foglio": leaflet.titolo,
        "source_url": source_url,
        "fetched_at": fetched_at,
    }
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def render_markdown(
    leaflet: LeafletText,
    meta: dict,
    source_url: str = "",
    fetched_at: str = "",
) -> str:
    toc = parse_toc(leaflet.body)
    sections = split_sections(leaflet.body, toc)

    out = [_front_matter(meta, leaflet, source_url, fetched_at), "", f"# {leaflet.titolo}", ""]

    def push_heading(text: str) -> None:
        if out and out[-1] != "":
            out.append("")
        out.append(text)
        out.append("")

    for number in range(1, 7):
        title = toc.get(number) or DEFAULT_TITLES[number]
        push_heading(f"## {number}. {title}")
        body = sections.get(number, "")
        if not body.strip():
            continue
        for subsection in detect_subsections(body, number):
            if subsection.title:
                push_heading(f"### {subsection.title}")
            out.extend(render_blocks(subsection.text))

    deduped: list[str] = []
    last_page: str | None = None
    for line in out:
        marker = re.fullmatch(r"<!-- page: (\d+) -->", line)
        if marker:
            if marker.group(1) == last_page:
                continue
            last_page = marker.group(1)
        deduped.append(line)

    while deduped and (
        not deduped[-1].strip() or re.fullmatch(r"<!-- page: \d+ -->", deduped[-1])
    ):
        deduped.pop()

    text = "\n".join(deduped)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def write_markdown(
    leaflet: LeafletText,
    meta: dict,
    out_dir: Path,
    index: int,
    source_url: str = "",
    fetched_at: str = "",
) -> Path:
    drug_dir = out_dir / str(meta.get("drug_id", "unknown"))
    drug_dir.mkdir(parents=True, exist_ok=True)
    path = drug_dir / f"{index:02d}.md"
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(render_markdown(leaflet, meta, source_url, fetched_at), encoding="utf-8")
    tmp.replace(path)
    return path
