// Client API same-origin: il browser chiama sempre le route proxy di Next.

export interface FarmacoPreview {
  id: string
  nome: string
  principio_attivo: string
}

export interface FarmacoDetail extends FarmacoPreview {
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
  listFarmaci: (): Promise<FarmacoPreview[]> => fetchJSON("/api/farmaci"),

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
}
