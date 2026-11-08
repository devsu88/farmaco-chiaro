"""Schemi Pydantic condivisi tra route e servizi."""
from __future__ import annotations

from pydantic import BaseModel, Field


class FarmacoPreview(BaseModel):
    id: str
    nome: str
    principio_attivo: str


class FarmacoDetail(FarmacoPreview):
    sezioni: dict[str, str]


class SearchResult(BaseModel):
    id: str
    nome: str
    principio_attivo: str
    score: float
    motivo: str


class SearchResponse(BaseModel):
    query: str
    risultati: list[SearchResult] = Field(default_factory=list)


class FonteCitata(BaseModel):
    blocco_id: str | None = None
    documento: str
    sezione: str
    paragrafo: str
    testo_evidenziato: str
    verificata: bool = True


class BloccoDocumento(BaseModel):
    blocco_id: str
    paragrafo: str
    testo: str


class SezioneDocumento(BaseModel):
    titolo: str
    blocchi: list[BloccoDocumento] = Field(default_factory=list)


class DocumentoResponse(BaseModel):
    farmaco_id: str
    documento: str
    sezioni: list[SezioneDocumento] = Field(default_factory=list)


class SimplifyRequest(BaseModel):
    farmaco_id: str
    sezione: str = "tutta"
    testo: str | None = None
    forza: bool = False


class EntitaVerificate(BaseModel):
    dosaggi_preservati: bool = False
    note: str = ""


class VoceGlossario(BaseModel):
    termine: str
    spiegazione: str


class SimplifyResponse(BaseModel):
    una_frase: str
    versione_facile: list[str] = Field(default_factory=list)
    glossario: list[VoceGlossario] = Field(default_factory=list)
    domande_farmacista: list[str] = Field(default_factory=list)
    entita_verificate: EntitaVerificate = Field(default_factory=EntitaVerificate)
    errore: str | None = None
    cached: bool = False


class ChatMessage(BaseModel):
    ruolo: str
    testo: str


class ChatRequest(BaseModel):
    farmaco_id: str
    messaggio: str
    storico: list[ChatMessage] = Field(default_factory=list)
    sessione_id: str | None = None


class ChatResponse(BaseModel):
    risposta: str
    fonti: list[FonteCitata] = Field(default_factory=list)
    sessione_id: str
    fallback_usato: bool = False


class SchermataGuida(BaseModel):
    id: str
    titolo: str
    icona: str
    descrizione: str
    testi: list[str] = Field(default_factory=list)
    fonti: list[FonteCitata] = Field(default_factory=list)


class GuidaResponse(BaseModel):
    farmaco_id: str
    nome: str
    principio_attivo: str
    documento: str
    schermate: list[SchermataGuida] = Field(default_factory=list)
    riepilogo: list[str] = Field(default_factory=list)


class ScenarioPreview(BaseModel):
    id: str
    titolo: str
    icona: str
    descrizione: str
    urgenza: str


class ScenariResponse(BaseModel):
    scenari: list[ScenarioPreview] = Field(default_factory=list)


class ScenarioRequest(BaseModel):
    farmaco_id: str


class ScenarioResponse(BaseModel):
    scenario_id: str
    farmaco_id: str
    titolo: str
    risposta: str
    azione: str
    urgenza: str
    trovato: bool
    fonti: list[FonteCitata] = Field(default_factory=list)


class SchedaResponse(BaseModel):
    farmaco_id: str
    nome: str
    principio_attivo: str
    documento: str
    a_cosa_serve: str
    come_si_prende: str
    cosa_non_fare: str
    quando_medico: str
    dose_dimenticata: str
    fonti: list[FonteCitata] = Field(default_factory=list)
    disclaimer: str
