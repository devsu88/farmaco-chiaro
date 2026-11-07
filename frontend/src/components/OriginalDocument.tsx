"use client"

import { useEffect, useMemo } from "react"
import { HighlightSpan } from "./HighlightSpan"
import type { DocumentoResponse, FonteCitata } from "@/lib/api"

interface OriginalDocumentProps {
  documento: DocumentoResponse | null
  fonte?: FonteCitata | null
  focusNonce?: number
}

export function OriginalDocument({
  documento,
  fonte,
  focusNonce = 0,
}: OriginalDocumentProps) {
  const bloccoAttivo = useMemo(() => {
    if (!documento || !fonte) return null

    const blocchi = documento.sezioni.flatMap((sezione) => sezione.blocchi)
    if (fonte.blocco_id && blocchi.some((b) => b.blocco_id === fonte.blocco_id)) {
      return fonte.blocco_id
    }

    const span = fonte.testo_evidenziato?.toLowerCase()
    if (!span) return null
    return (
      blocchi.find((b) => b.testo.toLowerCase().includes(span))?.blocco_id ?? null
    )
  }, [documento, fonte])

  useEffect(() => {
    if (!bloccoAttivo) return
    const elemento = document.getElementById(`blocco-${bloccoAttivo}`)
    elemento?.scrollIntoView({ behavior: "smooth", block: "center" })
  }, [bloccoAttivo, focusNonce])

  if (!documento) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-600">
        Documento originale non disponibile.
      </div>
    )
  }

  return (
    <section
      aria-label="Foglio illustrativo originale"
      className="bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-[65vh] overflow-y-auto"
    >
      <div className="mb-3 flex items-center gap-2 sticky top-0 bg-gray-50 pb-2">
        <span className="w-2 h-2 rounded-full bg-gray-400" />
        <span className="text-xs font-medium text-gray-600 uppercase tracking-wider">
          {documento.documento}
        </span>
      </div>

      <div className="prose prose-sm text-gray-800">
        {documento.sezioni.map((sezione) => (
          <section key={sezione.titolo} className="mb-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-2">
              {sezione.titolo}
            </h3>
            {sezione.blocchi.map((blocco) => {
              const attivo = blocco.blocco_id === bloccoAttivo
              return (
                <div
                  key={blocco.blocco_id}
                  id={`blocco-${blocco.blocco_id}`}
                  className={`mb-3 whitespace-pre-line rounded px-1 ${
                    attivo ? "bg-yellow-50 ring-1 ring-yellow-200" : ""
                  }`}
                >
                  {attivo && fonte ? (
                    <HighlightSpan
                      testo={blocco.testo}
                      evidenzia={fonte.testo_evidenziato}
                    />
                  ) : (
                    blocco.testo
                  )}
                </div>
              )
            })}
          </section>
        ))}
      </div>

      {fonte && (
        <div className="mt-3 p-2 bg-blue-50 rounded border border-blue-100">
          <p className="text-xs font-medium text-blue-800">
            Fonte citata: {fonte.sezione}, paragrafo {fonte.paragrafo}
            {fonte.verificata === false ? " (non verificata)" : ""}
          </p>
        </div>
      )}
    </section>
  )
}
