// Cronologia delle ultime ricerche, solo su questo dispositivo.
// Ogni voce conserva l'id del foglio: il nome da solo non basta a riaprire
// il farmaco giusto (lo stesso nome ha più formulazioni nel dataset).
//
// Il modulo si comporta anche da external store per useSyncExternalStore:
// lo snapshot del server è sempre vuoto, quello del client legge lo storage
// solo dopo l'idratazione (niente disallineamenti).

const CHIAVE = "fc-ricerche-recenti"
const MAX_RICERCHE = 3
const EVENTO = "fc-ricerche-recenti-cambiate"
const NESSUNA: RicercaRecente[] = []

export interface RicercaRecente {
  id: string
  nome: string
}

function validaRicerca(valore: unknown): valore is RicercaRecente {
  if (typeof valore !== "object" || valore === null) return false

  const { id, nome } = valore as { id?: unknown; nome?: unknown }
  return (
    typeof id === "string" &&
    id.trim() !== "" &&
    typeof nome === "string" &&
    nome.trim() !== ""
  )
}

function notifica(): void {
  if (typeof window === "undefined") return
  window.dispatchEvent(new Event(EVENTO))
}

export function leggiRicercheRecenti(): RicercaRecente[] {
  try {
    const salvate = localStorage.getItem(CHIAVE)
    if (!salvate) return []

    const valori: unknown = JSON.parse(salvate)
    if (!Array.isArray(valori)) return []

    return valori.filter(validaRicerca).slice(0, MAX_RICERCHE)
  } catch {
    // storage non disponibile: nessuna cronologia da mostrare
    return []
  }
}

export function aggiungiRicercaRecente(ricerca: RicercaRecente): void {
  const id = ricerca.id.trim()
  const nome = ricerca.nome.trim()
  if (!id || !nome) return

  try {
    const precedenti = leggiRicercheRecenti().filter((voce) => voce.id !== id)
    localStorage.setItem(
      CHIAVE,
      JSON.stringify([{ id, nome }, ...precedenti].slice(0, MAX_RICERCHE))
    )
    notifica()
  } catch {
    // storage non disponibile: la ricerca resta utilizzabile senza cronologia
  }
}

export function cancellaRicercheRecenti(): void {
  try {
    localStorage.removeItem(CHIAVE)
    notifica()
  } catch {
    // storage non disponibile: non c'è nulla da cancellare
  }
}

export function subscribeRicercheRecenti(callback: () => void): () => void {
  window.addEventListener("storage", callback)
  window.addEventListener(EVENTO, callback)
  return () => {
    window.removeEventListener("storage", callback)
    window.removeEventListener(EVENTO, callback)
  }
}

// Lo snapshot deve mantenere la stessa identità finché lo storage non cambia,
// altrimenti useSyncExternalStore entra in un ciclo di render infinito.
let cacheGrezzo: string | null = null
let cacheValore: RicercaRecente[] = NESSUNA
let cachePronta = false

export function getRicercheRecentiSnapshot(): RicercaRecente[] {
  let grezzo: string | null = null
  try {
    grezzo = localStorage.getItem(CHIAVE)
  } catch {
    grezzo = null
  }

  if (!cachePronta || grezzo !== cacheGrezzo) {
    cachePronta = true
    cacheGrezzo = grezzo
    cacheValore = leggiRicercheRecenti()
  }

  return cacheValore
}

export function getRicercheRecentiServerSnapshot(): RicercaRecente[] {
  return NESSUNA
}
