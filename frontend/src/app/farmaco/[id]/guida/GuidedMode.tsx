"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { api, type GuidaResponse } from "@/lib/api"
import {
  IconaArrowLeft,
  IconaArrowRight,
  IconaCheckCircle,
  IconaContrasto,
  IconaGuida,
  IconaShare,
  IconaTestoGrande,
  IconaVolume2,
} from "@/components/Icone"
import { Skeleton } from "@/components/Skeleton"
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
      <div
        aria-busy="true"
        className="min-h-screen bg-[#fbfcfe] flex flex-col items-center justify-center p-8"
      >
        <Skeleton className="h-8 w-48 mb-6" />
        <Skeleton className="h-72 w-full max-w-3xl" />
        <p className="sr-only">Preparo il percorso guidato...</p>
      </div>
    )
  }

  if (error || !guida) {
    return (
      <div className="min-h-screen bg-[#fbfcfe] flex flex-col items-center justify-center p-8">
        <div
          role="alert"
          className="max-w-md bg-white border border-gray-200 border-l-[3px] border-l-red-600 rounded-md p-6"
        >
          <h1 className="text-lg font-semibold text-red-900 mb-2">
            Guida non disponibile
          </h1>
          <p className="text-sm text-red-800 mb-4">{error}</p>
          <Link
            href={`/farmaco/${farmacoId}`}
            className="inline-flex items-center gap-1.5 border-b-2 border-blue-600 pb-0.5 text-sm font-semibold uppercase tracking-wider text-blue-800 hover:text-blue-900 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-sm"
          >
            <IconaArrowLeft size={14} />
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

  // Palette: superfici bianche e bordi sottili nel tema normale; nero/giallo
  // nell'alto contrasto. Le azioni primarie diventano link-azioni, l'unico
  // bottone pieno è "Avanti" (scuro, giallo nell'alto contrasto).
  const classiContenitore = contrasto
    ? "bg-black text-yellow-100"
    : "bg-[#fbfcfe] text-gray-900"
  const classiCard = contrasto
    ? "bg-black border-yellow-300 text-yellow-100"
    : "bg-white border-gray-200 text-gray-900"
  const classiTesto = testoGrande ? "text-2xl md:text-3xl" : "text-lg md:text-xl"
  const classiAzioneAscolta = contrasto
    ? "border-yellow-300 text-yellow-100"
    : "border-green-700 text-green-800"
  const classiEtichettaTecnica = contrasto
    ? "text-yellow-100/80"
    : "text-gray-500"
  const classiPulsantiAccessibilita = contrasto
    ? "border-yellow-300 text-yellow-100"
    : "border-gray-200 text-gray-600"
  const classiPulsanteAvanti = contrasto
    ? "bg-yellow-300 text-black hover:bg-yellow-200"
    : "bg-gray-900 text-white hover:bg-gray-800"
  const classiIconaSchermata = contrasto ? "text-yellow-100" : "text-blue-600"

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
              className="inline-flex items-center gap-1.5 border-b border-blue-600 pb-0.5 text-sm text-blue-800 hover:text-blue-900 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-sm"
            >
              <IconaArrowLeft size={14} />
              Torna al foglio
            </Link>
            <span className="text-sm font-medium">{guida.nome}</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setTestoGrande((valore) => !valore)}
              aria-pressed={testoGrande}
              className={`inline-flex items-center gap-1.5 border px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-wider rounded-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${classiPulsantiAccessibilita}`}
            >
              <IconaTestoGrande size={12} />
              {testoGrande ? "Testo normale" : "Testo grande"}
            </button>
            <button
              onClick={() => setContrasto((valore) => !valore)}
              aria-pressed={contrasto}
              className={`inline-flex items-center gap-1.5 border px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-wider rounded-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${classiPulsantiAccessibilita}`}
            >
              <IconaContrasto size={12} />
              {contrasto ? "Contrasto normale" : "Alto contrasto"}
            </button>
          </div>
        </div>
        <div
          className="h-1.5 bg-gray-200"
          role="progressbar"
          aria-valuenow={passo}
          aria-valuemin={1}
          aria-valuemax={totale}
          aria-label="Avanzamento del percorso"
        >
          <div
            className={`h-1.5 transition-all ${contrasto ? "bg-yellow-300" : "bg-blue-600"}`}
            style={{ width: `${(passo / totale) * 100}%` }}
          />
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        <p
          className={`text-[10px] font-semibold uppercase tracking-wider mb-2 ${classiEtichettaTecnica}`}
        >
          Passo {passo} di {totale}
        </p>

        <section
          aria-live="polite"
          className={`rounded-md border p-6 md:p-10 ${classiCard}`}
        >
          {schermata ? (
            <>
              <div className="mb-4" aria-hidden="true">
                <IconaGuida nome={schermata.icona} size={32} className={classiIconaSchermata} />
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

              <div className="mt-6 flex flex-wrap items-center gap-4">
                <button
                  onClick={() => speak(testoSchermata)}
                  disabled={ttsLoading}
                  className={`inline-flex items-center gap-1.5 border-b-2 pb-0.5 text-sm font-semibold uppercase tracking-wider hover:opacity-80 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-green-500 rounded-sm ${classiAzioneAscolta}`}
                >
                  <IconaVolume2 size={14} />
                  {ttsLoading ? "Preparo l'audio..." : speaking ? "Riascolta" : "Ascolta"}
                </button>
                {speaking && (
                  <button
                    onClick={stop}
                    className={`px-3 py-1.5 border rounded-sm text-sm font-medium focus:outline-none focus:ring-2 focus:ring-gray-400 ${
                      contrasto
                        ? "border-yellow-300 text-yellow-100"
                        : "border-gray-300 text-gray-700"
                    }`}
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
                  className={`mt-6 rounded-md border p-4 text-sm ${
                    contrasto ? "border-yellow-300" : "border-gray-200 bg-gray-50"
                  }`}
                >
                  <summary className="cursor-pointer font-medium">
                    Vedi la fonte nel foglio illustrativo
                  </summary>
                  <blockquote className="mt-3 italic border-l-2 border-gray-300 pl-3">
                    “{fonte.testo_evidenziato}”
                  </blockquote>
                  <p className={`mt-2 text-xs ${classiEtichettaTecnica}`}>
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
              <div className="mb-4" aria-hidden="true">
                <IconaCheckCircle size={32} className={contrasto ? "text-yellow-100" : "text-green-700"} />
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

              <div className="mt-8 flex flex-wrap items-center gap-4">
                <button
                  onClick={() => speak(testoSchermata)}
                  disabled={ttsLoading}
                  className={`inline-flex items-center gap-1.5 border-b-2 pb-0.5 text-sm font-semibold uppercase tracking-wider hover:opacity-80 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-green-500 rounded-sm ${classiAzioneAscolta}`}
                >
                  <IconaVolume2 size={14} />
                  {ttsLoading ? "Preparo l'audio..." : speaking ? "Riascolta" : "Ascolta tutto"}
                </button>
                <Link
                  href={`/scheda/${farmacoId}`}
                  className={`inline-flex items-center gap-1.5 border-b-2 pb-0.5 text-sm font-semibold uppercase tracking-wider hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-sm ${
                    contrasto
                      ? "border-yellow-300 text-yellow-100"
                      : "border-blue-600 text-blue-800"
                  }`}
                >
                  <IconaShare size={14} />
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
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-40 rounded-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <IconaArrowLeft size={14} />
            Indietro
          </button>
          {!riepilogo ? (
            <button
              onClick={() => vaiA(indice + 1)}
              className={`inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold uppercase tracking-wider rounded-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${classiPulsanteAvanti}`}
            >
              {indice === schermate.length - 1 ? "Vedi il riepilogo" : "Avanti"}
              <IconaArrowRight size={14} />
            </button>
          ) : (
            <Link
              href={`/farmaco/${farmacoId}`}
              className={`inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold uppercase tracking-wider rounded-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${classiPulsanteAvanti}`}
            >
              Torna al foglio
              <IconaArrowRight size={14} />
            </Link>
          )}
        </nav>

        <p
          className={`text-xs mt-8 text-center ${
            contrasto ? "text-yellow-100/70" : "text-gray-500"
          }`}
        >
          La guida riporta il testo del foglio illustrativo AIFA. Non sostituisce
          il medico o il farmacista.
        </p>
      </main>
    </div>
  )
}
