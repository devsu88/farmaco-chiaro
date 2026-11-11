// Client API same-origin: il browser chiama sempre le route proxy di Next.

export interface FarmacoDetail {
  id: string
  nome: string
  principio_attivo: string
  sezioni: Record<string, string>
}

export interface SearchResult {
  id: string
  nome: string
  principio_attivo: string
  score: number
  motivo: string
}

export interface SearchResponse {
  query: string
  risultati: SearchResult[]
}

export interface BloccoDocumento {
  blocco_id: string
  paragrafo: string
  testo: string
}

export interface SezioneDocumento {
  titolo: string
  blocchi: BloccoDocumento[]
}

export interface DocumentoResponse {
  farmaco_id: string
  documento: string
  sezioni: SezioneDocumento[]
}

export interface SimplifyResponse {
  una_frase: string
  versione_facile: string[]
  glossario: { termine: string; spiegazione: string }[]
  domande_farmacista: string[]
  entita_verificate: {
    dosaggi_preservati: boolean
    note: string
  }
  errore?: string
  cached?: boolean
}

export interface FonteCitata {
  blocco_id?: string | null
  documento: string
  sezione: string
  paragrafo: string
  testo_evidenziato: string
  verificata?: boolean
}

export interface ChatResponse {
  risposta: string
  fonti: FonteCitata[]
  sessione_id: string
  fallback_usato: boolean
}

export interface SchermataGuida {
  id: string
  titolo: string
  icona: string
  descrizione: string
  testi: string[]
  fonti: FonteCitata[]
}

export interface GuidaResponse {
  farmaco_id: string
  nome: string
  principio_attivo: string
  documento: string
  schermate: SchermataGuida[]
  riepilogo: string[]
}

export interface ScenarioPreview {
  id: string
  titolo: string
  icona: string
  descrizione: string
  urgenza: "normale" | "contatta_medico" | "emergenza"
}

export interface ScenariResponse {
  scenari: ScenarioPreview[]
}

export interface ScenarioResponse {
  scenario_id: string
  farmaco_id: string
  titolo: string
  risposta: string
  azione: string
  urgenza: "normale" | "contatta_medico" | "emergenza"
  trovato: boolean
  fonti: FonteCitata[]
}

export interface SchedaResponse {
  farmaco_id: string
  nome: string
  principio_attivo: string
  documento: string
  a_cosa_serve: string
  come_si_prende: string
  cosa_non_fare: string
  quando_medico: string
  dose_dimenticata: string
  dose_dimenticata_trovata: boolean
  fonti: FonteCitata[]
  disclaimer: string
}

async function fetchJSON<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const res = await fetch(input, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
    ...init,
  })

  if (!res.ok) {
    let messaggio = `Errore API ${res.status}`
    try {
      const body = await res.json()
      messaggio = body?.error?.message || body?.detail || messaggio
    } catch {
      // risposta non JSON: manteniamo il messaggio generico
    }
    throw new Error(messaggio)
  }

  return res.json()
}

export const api = {
  getFarmaco: (id: string): Promise<FarmacoDetail> =>
    fetchJSON(`/api/farmaco/${encodeURIComponent(id)}`),

  getDocumento: (id: string): Promise<DocumentoResponse> =>
    fetchJSON(`/api/farmaco/${encodeURIComponent(id)}/documento`),

  search: (q: string): Promise<SearchResponse> =>
    fetchJSON(`/api/search?q=${encodeURIComponent(q)}`),

  simplify: (body: {
    farmaco_id: string
    sezione?: string
    testo?: string
    forza?: boolean
  }): Promise<SimplifyResponse> =>
    fetchJSON("/api/simplify", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  chat: (body: {
    farmaco_id: string
    messaggio: string
    storico: { ruolo: string; testo: string }[]
    sessione_id?: string
  }): Promise<ChatResponse> =>
    fetchJSON("/api/chat", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getGuida: (id: string): Promise<GuidaResponse> =>
    fetchJSON(`/api/farmaco/${encodeURIComponent(id)}/guida`),

  getScheda: (id: string): Promise<SchedaResponse> =>
    fetchJSON(`/api/farmaco/${encodeURIComponent(id)}/scheda`),

  getScenari: (): Promise<ScenariResponse> => fetchJSON("/api/scenari"),

  risolviScenario: (
    scenarioId: string,
    farmacoId: string
  ): Promise<ScenarioResponse> =>
    fetchJSON(`/api/scenari/${encodeURIComponent(scenarioId)}`, {
      method: "POST",
      body: JSON.stringify({ farmaco_id: farmacoId }),
    }),
}
