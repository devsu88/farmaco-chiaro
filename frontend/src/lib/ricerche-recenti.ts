// Cronologia delle ultime ricerche, solo su questo dispositivo.

const CHIAVE = "fc-ricerche-recenti"
const MAX_RICERCHE = 3

export function leggiRicercheRecenti(): string[] {
  try {
    const salvate = localStorage.getItem(CHIAVE)
    if (!salvate) return []

    const valori: unknown = JSON.parse(salvate)
    if (!Array.isArray(valori)) return []

    return valori
      .filter((valore): valore is string => typeof valore === "string")
      .slice(0, MAX_RICERCHE)
  } catch {
    // storage non disponibile: nessuna cronologia da mostrare
    return []
  }
}

export function aggiungiRicercaRecente(nome: string): void {
  const pulito = nome.trim()
  if (!pulito) return

  try {
    const precedenti = leggiRicercheRecenti().filter((voce) => voce !== pulito)
    localStorage.setItem(
      CHIAVE,
      JSON.stringify([pulito, ...precedenti].slice(0, MAX_RICERCHE))
    )
  } catch {
    // storage non disponibile: la ricerca resta utilizzabile senza cronologia
  }
}

export function cancellaRicercheRecenti(): void {
  try {
    localStorage.removeItem(CHIAVE)
  } catch {
    // storage non disponibile: non c'è nulla da cancellare
  }
}
