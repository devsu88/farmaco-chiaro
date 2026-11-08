"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import {
  api,
  type FonteCitata,
  type ScenarioPreview,
  type ScenarioResponse,
} from "@/lib/api"
import { icona } from "@/lib/icone"
import { useTTS } from "@/hooks/useTTS"

interface ScenarioWizardProps {
  farmacoId: string
  open: boolean
  onClose: () => void
  onHighlightSource?: (fonte: FonteCitata) => void
}

const URGENZE = {
  normale: {
    etichetta: "Situazione non urgente",
    classi: "bg-green-50 text-green-900 border-green-200",
  },
  contatta_medico: {
    etichetta: "Contatta il medico",
    classi: "bg-amber-50 text-amber-900 border-amber-200",
  },
  emergenza: {
    etichetta: "Possibile emergenza",
    classi: "bg-red-50 text-red-900 border-red-200",
  },
}

export function ScenarioWizard({
  farmacoId,
  open,
  onClose,
  onHighlightSource,
}: ScenarioWizardProps) {
  const [scenari, setScenari] = useState<ScenarioPreview[]>([])
  const [risultato, setRisultato] = useState<ScenarioResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const { speak, stop, speaking, loading: ttsLoading, error: ttsError } = useTTS()

  useEffect(() => {
    if (!open) return
    closeRef.current?.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [open, onClose])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    api
      .getScenari()
      .then((risposta) => {
        if (!cancelled) setScenari(risposta.scenari)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Scenari non disponibili"
          )
        }
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const scegli = async (scenarioId: string) => {
    setLoading(true)
    setError(null)
    try {
      setRisultato(await api.risolviScenario(scenarioId, farmacoId))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Risposta non disponibile")
    } finally {
      setLoading(false)
    }
  }

  const ricomincia = () => {
    stop()
    setRisultato(null)
    setError(null)
  }

  const chiudi = () => {
    stop()
    setRisultato(null)
    setError(null)
    onClose()
  }

  if (!open) return null

  const urgenza = risultato ? URGENZE[risultato.urgenza] : null

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 p-0 sm:p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) chiudi()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="scenario-titolo"
        className="w-full sm:max-w-lg max-h-[92vh] overflow-y-auto bg-white rounded-t-2xl sm:rounded-2xl shadow-xl"
      >
        <div className="sticky top-0 bg-white border-b border-gray-100 p-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="scenario-titolo" className="text-xl font-bold text-gray-900">
              Cosa faccio se…?
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Scegli una situazione. La risposta cita il foglio illustrativo.
            </p>
          </div>
          <button
            ref={closeRef}
            onClick={chiudi}
            aria-label="Chiudi"
            className="p-2 text-gray-500 hover:text-gray-700 rounded hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            ✕
          </button>
        </div>

        <div className="p-4">
          {error && (
            <p
              role="alert"
              className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-800"
            >
              {error}
            </p>
          )}

          {loading && (
            <div className="py-10 flex flex-col items-center">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mb-3" />
              <p className="text-sm text-gray-600">Cerco nel foglio illustrativo...</p>
            </div>
          )}

          {!loading && !risultato && (
            <>
              {scenari.length === 0 && !error && (
                <p className="text-sm text-gray-500">Carico gli scenari...</p>
              )}
              <ul className="space-y-2">
                {scenari.map((scenario) => (
                  <li key={scenario.id}>
                    <button
                      onClick={() => scegli(scenario.id)}
                      className="w-full text-left p-4 border border-gray-200 rounded-xl hover:border-blue-400 hover:bg-blue-50 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <span className="text-2xl mr-3" aria-hidden="true">
                        {icona(scenario.icona)}
                      </span>
                      <span className="font-semibold text-gray-900">
                        {scenario.titolo}
                      </span>
                      <span className="block text-sm text-gray-600 mt-1 ml-9">
                        {scenario.descrizione}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}

          {!loading && risultato && (
            <div>
              {urgenza && (
                <p
                  className={`inline-block text-xs font-semibold px-3 py-1 rounded-full border mb-3 ${urgenza.classi}`}
                >
                  {urgenza.etichetta}
                </p>
              )}
              <h3 className="text-lg font-bold text-gray-900 mb-2">
                {risultato.titolo}
              </h3>

              <blockquote className="text-base leading-relaxed text-gray-800 bg-gray-50 border-l-4 border-blue-500 rounded-r-lg p-4 whitespace-pre-line">
                {risultato.risposta}
              </blockquote>

              <div className="mt-4 p-4 bg-blue-50 border border-blue-100 rounded-lg">
                <h4 className="text-sm font-semibold text-blue-900 mb-1">
                  Cosa fare
                </h4>
                <p className="text-sm text-blue-900 leading-relaxed">
                  {risultato.azione}
                </p>
              </div>

              {risultato.fonti.length > 0 && (
                <div className="mt-4 space-y-2">
                  {risultato.fonti.map((fonte, indice) => (
                    <button
                      key={`${fonte.blocco_id ?? "fonte"}-${indice}`}
                      onClick={() => {
                        onHighlightSource?.(fonte)
                        chiudi()
                      }}
                      className="block text-left text-sm text-blue-700 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
                    >
                      Vai alla fonte: {fonte.sezione}
                      {fonte.paragrafo ? `, ${fonte.paragrafo}` : ""}
                    </button>
                  ))}
                </div>
              )}

              {!risultato.trovato && (
                <p className="mt-3 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-3">
                  Il foglio non riporta un passaggio specifico per questa
                  situazione. La risposta è un&apos;indicazione generale di
                  sicurezza.
                </p>
              )}

              <div className="mt-5 flex flex-wrap gap-2">
                <button
                  onClick={() =>
                    speak(`${risultato.risposta} ${risultato.azione}`)
                  }
                  disabled={ttsLoading}
                  className="px-4 py-2.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-green-500"
                >
                  {ttsLoading ? "Preparo l'audio..." : speaking ? "Riascolta" : "Ascolta"}
                </button>
                <Link
                  href={`/scheda/${farmacoId}`}
                  className="px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  Invia a un familiare
                </Link>
                <button
                  onClick={ricomincia}
                  className="px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400"
                >
                  Un altro scenario
                </button>
              </div>
              {ttsError && (
                <p role="alert" className="text-sm text-red-600 mt-2">
                  {ttsError}
                </p>
              )}
            </div>
          )}

          <p className="text-[11px] text-gray-500 mt-6 text-center">
            Questa guida non sostituisce il medico o il farmacista. In caso di
            sintomi gravi chiama il 112.
          </p>
        </div>
      </div>
    </div>
  )
}
