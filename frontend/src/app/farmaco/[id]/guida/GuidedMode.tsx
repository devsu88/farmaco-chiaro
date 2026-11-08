"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { api, type GuidaResponse } from "@/lib/api"
import { icona } from "@/lib/icone"
import { useTTS } from "@/hooks/useTTS"

export function GuidedMode({ farmacoId }: { farmacoId: string }) {
  const [guida, setGuida] = useState<GuidaResponse | null>(null)
  const [indice, setIndice] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [contrasto, setContrasto] = useState(false)
  const [testoGrande, setTestoGrande] = useState(true)
  const titoloRef = useRef<HTMLHeadingElement>(null)
  const { speak, stop, speaking, loading: ttsLoading, error: ttsError } = useTTS()

  useEffect(() => {
    let cancelled = false
    api
      .getGuida(farmacoId)
      .then((risultato) => {
        if (!cancelled) setGuida(risultato)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Guida non disponibile"
          )
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [farmacoId])

  useEffect(() => {
    titoloRef.current?.focus()
  }, [indice, guida])

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-8">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4" />
        <p className="text-gray-700">Preparo il percorso guidato...</p>
      </div>
    )
  }

  if (error || !guida) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-8">
        <div role="alert" className="max-w-md bg-red-50 border border-red-200 rounded-lg p-6">
          <h1 className="text-lg font-semibold text-red-900 mb-2">
            Guida non disponibile
          </h1>
          <p className="text-sm text-red-800 mb-4">{error}</p>
          <Link
            href={`/farmaco/${farmacoId}`}
            className="inline-block px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Torna al foglio illustrativo
          </Link>
        </div>
      </div>
    )
  }

  const schermate = guida.schermate
  const riepilogo = indice >= schermate.length
  const schermata = riepilogo ? null : schermate[indice]
  const totale = schermate.length + 1
  const passo = indice + 1
  const testoSchermata = schermata
    ? [schermata.titolo, ...schermata.testi].join(" ")
    : ["Riepilogo", ...guida.riepilogo].join(" ")

  const classiContenitore = contrasto
    ? "bg-black text-yellow-100"
    : "bg-gray-50 text-gray-900"
  const classiCard = contrasto
    ? "bg-black border-yellow-300 text-yellow-100"
    : "bg-white border-gray-200 text-gray-900"
  const classiTesto = testoGrande ? "text-2xl md:text-3xl" : "text-lg md:text-xl"

  const vaiA = (nuovoIndice: number) => {
    stop()
    setIndice(Math.max(0, Math.min(nuovoIndice, totale - 1)))
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  return (
    <div className={`min-h-screen ${classiContenitore}`}>
      <header
        className={`border-b sticky top-0 z-20 ${
          contrasto ? "bg-black border-yellow-300" : "bg-white border-gray-200"
        }`}
      >
        <div className="max-w-3xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <Link
              href={`/farmaco/${farmacoId}`}
              className="text-sm underline underline-offset-2 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
            >
              ← Torna al foglio
            </Link>
            <span className="text-sm font-medium">{guida.nome}</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setTestoGrande((valore) => !valore)}
              aria-pressed={testoGrande}
              className="px-3 py-1.5 text-xs font-medium border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {testoGrande ? "Testo normale" : "Testo grande"}
            </button>
            <button
              onClick={() => setContrasto((valore) => !valore)}
              aria-pressed={contrasto}
              className="px-3 py-1.5 text-xs font-medium border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {contrasto ? "Contrasto normale" : "Alto contrasto"}
            </button>
          </div>
        </div>
        <div
          className="h-2 bg-gray-200"
          role="progressbar"
          aria-valuenow={passo}
          aria-valuemin={1}
          aria-valuemax={totale}
          aria-label="Avanzamento del percorso"
        >
          <div
            className="h-2 bg-blue-600 transition-all"
            style={{ width: `${(passo / totale) * 100}%` }}
          />
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        <p className="text-sm font-medium mb-2">
          Passo {passo} di {totale}
        </p>

        <section
          aria-live="polite"
          className={`rounded-2xl border p-6 md:p-10 shadow-sm ${classiCard}`}
        >
          {schermata ? (
            <>
              <div className="text-5xl mb-4" aria-hidden="true">
                {icona(schermata.icona)}
              </div>
              <h1
                ref={titoloRef}
                tabIndex={-1}
                className="text-3xl md:text-4xl font-bold mb-4 outline-none"
              >
                {schermata.titolo}
              </h1>
              <p className={`${classiTesto} leading-relaxed whitespace-pre-line`}>
                {schermata.testi.join("\n\n")}
              </p>

              <div className="mt-6 flex flex-wrap gap-2">
                <button
                  onClick={() => speak(testoSchermata)}
                  disabled={ttsLoading}
                  className="px-4 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-green-500"
                >
                  {ttsLoading ? "Preparo l'audio..." : speaking ? "Riascolta" : "Ascolta"}
                </button>
                {speaking && (
                  <button
                    onClick={stop}
                    className="px-4 py-3 border rounded-lg font-medium focus:outline-none focus:ring-2 focus:ring-gray-400"
                  >
                    Ferma
                  </button>
                )}
              </div>
              {ttsError && (
                <p role="alert" className="text-sm text-red-600 mt-2">
                  {ttsError}
                </p>
              )}

              {schermata.fonti.map((fonte, posizione) => (
                <details
                  key={`${fonte.blocco_id ?? "fonte"}-${posizione}`}
                  className={`mt-6 rounded-lg border p-4 text-sm ${
                    contrasto ? "border-yellow-300" : "border-gray-200 bg-gray-50"
                  }`}
                >
                  <summary className="cursor-pointer font-medium">
                    Vedi la fonte nel foglio illustrativo
                  </summary>
                  <blockquote className="mt-3 italic">
                    “{fonte.testo_evidenziato}”
                  </blockquote>
                  <p className="mt-2 text-xs opacity-80">
                    {fonte.sezione}
                    {fonte.paragrafo ? `, ${fonte.paragrafo}` : ""}
                  </p>
                  <Link
                    href={`/farmaco/${farmacoId}?fonte=${encodeURIComponent(
                      fonte.blocco_id ?? ""
                    )}`}
                    className="inline-block mt-3 underline underline-offset-2"
                  >
                    Apri nel foglio originale
                  </Link>
                </details>
              ))}
            </>
          ) : (
            <>
              <div className="text-5xl mb-4" aria-hidden="true">
                ✅
              </div>
              <h1
                ref={titoloRef}
                tabIndex={-1}
                className="text-3xl md:text-4xl font-bold mb-4 outline-none"
              >
                Riepilogo
              </h1>
              <ul className={`${classiTesto} space-y-3 list-disc pl-6`}>
                {guida.riepilogo.map((frase) => (
                  <li key={frase}>{frase}</li>
                ))}
              </ul>

              <div className="mt-8 flex flex-wrap gap-2">
                <button
                  onClick={() => speak(testoSchermata)}
                  disabled={ttsLoading}
                  className="px-4 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-green-500"
                >
                  {ttsLoading ? "Preparo l'audio..." : speaking ? "Riascolta" : "Ascolta tutto"}
                </button>
                <Link
                  href={`/scheda/${farmacoId}`}
                  className="px-4 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  Invia a un familiare
                </Link>
              </div>
              {ttsError && (
                <p role="alert" className="text-sm text-red-600 mt-2">
                  {ttsError}
                </p>
              )}
            </>
          )}
        </section>

        <nav className="mt-6 flex items-center justify-between gap-3">
          <button
            onClick={() => vaiA(indice - 1)}
            disabled={indice === 0}
            className="px-5 py-3 rounded-lg border font-medium disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            ← Indietro
          </button>
          {!riepilogo ? (
            <button
              onClick={() => vaiA(indice + 1)}
              className="px-5 py-3 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {indice === schermate.length - 1 ? "Vedi il riepilogo" : "Avanti →"}
            </button>
          ) : (
            <Link
              href={`/farmaco/${farmacoId}`}
              className="px-5 py-3 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Torna al foglio
            </Link>
          )}
        </nav>

        <p className="text-xs opacity-70 mt-8 text-center">
          La guida riporta il testo del foglio illustrativo AIFA. Non sostituisce
          il medico o il farmacista.
        </p>
      </main>
    </div>
  )
}
