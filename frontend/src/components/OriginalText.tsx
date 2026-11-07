"use client"

import { HighlightSpan } from "./HighlightSpan"

interface OriginalTextProps {
  testo: string
  fonti?: { testo_evidenziato: string; sezione?: string; paragrafo?: string }[]
  classe?: string
}

export function OriginalText({ testo, fonti, classe = "" }: OriginalTextProps) {
  // Trova il primo span da evidenziare (se ci sono fonti)
  const spanDaEvidenziare = fonti?.[0]?.testo_evidenziato || null

  return (
    <div className={`${classe} bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-[60vh] overflow-y-auto text-sm leading-relaxed`}>
      <div className="mb-2 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-gray-400"></span>
        <span className="text-xs font-medium text-gray-600 uppercase tracking-wider">Foglio illustrativo AIFA (originale)</span>
      </div>
      <div className="prose prose-sm text-gray-800">
        <HighlightSpan testo={testo} evidenzia={spanDaEvidenziare} />
      </div>
      {fonti && fonti.length > 0 && (
        <div className="mt-3 p-2 bg-blue-50 rounded border border-blue-100">
          <p className="text-xs font-medium text-blue-800 mb-1">
            📍 Fonte citata dalla chat: {fonti[0].sezione}, paragrafo {fonti[0].paragrafo}
          </p>
        </div>
      )}
    </div>
  )
}