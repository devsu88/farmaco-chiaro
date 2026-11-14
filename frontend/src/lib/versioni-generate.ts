// Registro locale dei farmaci per cui l'utente ha già generato la versione facile.

const CHIAVE = "fc-versioni-generate"

export function versioneGiaGenerata(farmacoId: string): boolean {
  try {
    const salvate = localStorage.getItem(CHIAVE)
    if (!salvate) return false

    const registro: unknown = JSON.parse(salvate)
    return Array.isArray(registro) && registro.includes(farmacoId)
  } catch {
    // storage non disponibile: trattiamo il farmaco come mai generato
    return false
  }
}

export function registraVersioneGenerata(farmacoId: string): void {
  try {
    const salvate = localStorage.getItem(CHIAVE)
    const registro: unknown = salvate ? JSON.parse(salvate) : []

    const ids = Array.isArray(registro)
      ? registro.filter((valore): valore is string => typeof valore === "string")
      : []
    if (ids.includes(farmacoId)) return

    localStorage.setItem(CHIAVE, JSON.stringify([...ids, farmacoId]))
  } catch {
    // storage non disponibile: la versione resta visibile ma non viene ricordata
  }
}
