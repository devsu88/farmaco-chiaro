"use client"

import { useEffect, useState, useSyncExternalStore } from "react"
import Link from "next/link"
import QRCode from "qrcode"
import { api, type SchedaResponse } from "@/lib/api"

function Sezione({
  titolo,
  testo,
  icona,
}: {
  titolo: string
  testo: string
  icona: string
}) {
  return (
    <section className="border border-gray-200 rounded-xl p-4">
      <h2 className="text-sm font-semibold text-blue-900 uppercase tracking-wide mb-2">
        <span aria-hidden="true" className="mr-2">
          {icona}
        </span>
        {titolo}
      </h2>
      <p className="text-base text-gray-800 leading-relaxed whitespace-pre-line">
        {testo}
      </p>
    </section>
  )
}

export function ShareCard({ farmacoId }: { farmacoId: string }) {
  const [scheda, setScheda] = useState<SchedaResponse | null>(null)
  const [qr, setQr] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const url = useSyncExternalStore(
    () => () => {},
    () => window.location.href,
    () => ""
  )

  useEffect(() => {
    let cancelled = false
    api
      .getScheda(farmacoId)
      .then((risultato) => {
        if (!cancelled) setScheda(risultato)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Scheda non disponibile"
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
    if (!url) return
    QRCode.toDataURL(url, { width: 240, margin: 1 }).then(setQr).catch(() => {
      setQr(null)
    })
  }, [url])

  const condividi = async () => {
    if (!scheda) return
    const testo = `${scheda.nome}: scheda semplice con le informazioni principali e le fonti AIFA.`
    if (navigator.share) {
      try {
        await navigator.share({ title: scheda.nome, text: testo, url })
      } catch {
        // L'utente ha annullato: nessun errore da mostrare.
      }
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-8">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4" />
        <p className="text-gray-700">Preparo la scheda...</p>
      </div>
    )
  }

  if (error || !scheda) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-8">
        <div role="alert" className="max-w-md bg-red-50 border border-red-200 rounded-lg p-6">
          <h1 className="text-lg font-semibold text-red-900 mb-2">
            Scheda non disponibile
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

  const messaggioWhatsApp = encodeURIComponent(
    `${scheda.nome} — scheda semplice con le informazioni principali e le fonti AIFA: ${url}`
  )

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 print:hidden">
        <div className="max-w-3xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-2">
          <Link
            href={`/farmaco/${farmacoId}`}
            className="text-sm underline underline-offset-2 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
          >
            ← Torna al foglio
          </Link>
          <div className="flex gap-2">
            {typeof navigator !== "undefined" && "share" in navigator && (
              <button
                onClick={condividi}
                className="px-3 py-1.5 text-sm font-medium bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                Condividi
              </button>
            )}
            <a
              href={`https://wa.me/?text=${messaggioWhatsApp}`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 text-sm font-medium bg-green-600 text-white rounded hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500"
            >
              WhatsApp
            </a>
            <button
              onClick={() => window.print()}
              className="px-3 py-1.5 text-sm font-medium border border-gray-300 rounded hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400"
            >
              Stampa
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8 space-y-4">
        <div className="bg-white border border-gray-200 rounded-2xl p-6">
          <h1 className="text-3xl font-bold text-gray-900">{scheda.nome}</h1>
          <p className="text-sm text-gray-600 mt-1">
            Principio attivo: {scheda.principio_attivo}
          </p>
          <p className="text-xs text-gray-500 mt-2">{scheda.documento}</p>
        </div>

        <Sezione
          titolo="A cosa serve"
          icona="ℹ️"
          testo={scheda.a_cosa_serve}
        />
        <Sezione
          titolo="Come si prende"
          icona="💊"
          testo={scheda.come_si_prende}
        />
        <Sezione
          titolo="Cosa non fare"
          icona="🚫"
          testo={scheda.cosa_non_fare}
        />
        <Sezione
          titolo="Quando chiamare il medico"
          icona="📞"
          testo={scheda.quando_medico}
        />
        <Sezione
          titolo={
            scheda.dose_dimenticata_trovata
              ? "Se dimentica una dose"
              : "Se dimentica una dose (indicazione generale)"
          }
          icona="⏰"
          testo={scheda.dose_dimenticata}
        />
        {!scheda.dose_dimenticata_trovata && (
          <p className="-mt-2 px-1 text-xs text-amber-800">
            Il foglio illustrativo non riporta una regola specifica per la dose
            dimenticata: questo è un consiglio generale di sicurezza.
          </p>
        )}

        <div className="bg-white border border-gray-200 rounded-2xl p-6 flex flex-col sm:flex-row items-center gap-5">
          {qr ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={qr}
              alt="Codice QR per aprire questa scheda"
              width={180}
              height={180}
              className="rounded"
            />
          ) : (
            <div className="w-[180px] h-[180px] bg-gray-100 rounded flex items-center justify-center text-xs text-gray-500">
              QR non disponibile
            </div>
          )}
          <div>
            <h2 className="font-semibold text-gray-900 mb-1">
              Porta la scheda con te
            </h2>
            <p className="text-sm text-gray-600">
              Inquadra il QR con un altro telefono, oppure invia il link. La
              scheda è pubblica e non contiene dati personali.
            </p>
            <p className="text-xs text-gray-500 mt-2 break-all">{url}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 print:hidden">
          <Link
            href={`/farmaco/${farmacoId}`}
            className="px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Apri il foglio illustrativo originale
          </Link>
          <Link
            href={`/farmaco/${farmacoId}/guida`}
            className="px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400"
          >
            Percorso guidato
          </Link>
        </div>

        <p className="text-xs text-gray-500 border-t border-gray-200 pt-4">
          {scheda.disclaimer}
        </p>
        <p className="text-[11px] text-gray-400">
          I testi delle sezioni principali sono riportati dal foglio
          illustrativo AIFA; le indicazioni generali di sicurezza sono
          segnalate. Fonti: {scheda.fonti.length} passaggi del foglio.
        </p>
      </main>
    </div>
  )
}
