"use client"

interface HighlightSpanProps {
  testo: string
  evidenzia: string | null
  classeBase?: string
  classeEvidenzia?: string
}

export function HighlightSpan({ testo, evidenzia, classeBase = "", classeEvidenzia = "bg-yellow-200" }: HighlightSpanProps) {
  if (!evidenzia || evidenzia.trim() === "") {
    return <span className={classeBase}>{testo}</span>
  }

  // Trova la prima occorrenza di evidenzia nel testo (case-insensitive)
  const indice = testo.toLowerCase().indexOf(evidenzia.toLowerCase())

  if (indice === -1) {
    return <span className={classeBase}>{testo}</span>
  }

  const prima = testo.slice(0, indice)
  const parteEvidenziata = testo.slice(indice, indice + evidenzia.length)
  const dopo = testo.slice(indice + evidenzia.length)

  return (
    <span className={classeBase}>
      {prima}
      <mark className={`${classeEvidenzia} rounded px-0.5`}>{parteEvidenziata}</mark>
      {dopo}
    </span>
  )
}