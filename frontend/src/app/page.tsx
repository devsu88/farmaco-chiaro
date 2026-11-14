"use client"

import { useSyncExternalStore } from "react"
import { useRouter } from "next/navigation"
import { SearchBar } from "@/components/SearchBar"
import {
  IconaBookOpen,
  IconaCheckCircle,
  IconaHeadphones,
  IconaInfo,
  IconaX,
} from "@/components/Icone"
import { api } from "@/lib/api"
import { FARMACI_COMUNI, TOTALE_FARMACI } from "@/lib/farmaci-comuni"
import {
  aggiungiRicercaRecente,
  cancellaRicercheRecenti,
  getRicercheRecentiServerSnapshot,
  getRicercheRecentiSnapshot,
  subscribeRicercheRecenti,
  type RicercaRecente,
} from "@/lib/ricerche-recenti"

const FUNZIONI = [
  {
    icona: IconaBookOpen,
    coloreIcona: "text-blue-600",
    titolo: "Trova",
    descrizione: "Ricerca per nome o sintomo",
  },
  {
    icona: IconaCheckCircle,
    coloreIcona: "text-green-700",
    titolo: "Leggi",
    descrizione: "Solo l'essenziale, già verificato",
  },
  {
    icona: IconaHeadphones,
    coloreIcona: "text-blue-600",
    titolo: "Ascolta",
    descrizione: "Audio e chat con fonti",
  },
]

export default function Home() {
  const router = useRouter()
  // La cronologia vive in localStorage: lo snapshot del server è vuoto, quindi
  // il primo render del client coincide con quello del server e si aggiorna
  // solo dopo l'idratazione.
  const ricercheRecenti = useSyncExternalStore(
    subscribeRicercheRecenti,
    getRicercheRecentiSnapshot,
    getRicercheRecentiServerSnapshot
  )

  const ricordaFarmaco = (id: string) => {
    const comune = FARMACI_COMUNI.find((farmaco) => farmaco.id === id)
    if (comune) {
      aggiungiRicercaRecente(comune)
      return
    }

    // Dalla ricerca arriva solo l'id: il nome serve come etichetta della voce.
    // Se la richiesta fallisce, la navigazione resta senza cronologia.
    void api
      .getFarmaco(id)
      .then((farmaco) => aggiungiRicercaRecente({ id, nome: farmaco.nome }))
      .catch(() => undefined)
  }

  const apriFarmaco = (id: string) => {
    ricordaFarmaco(id)
    router.push(`/farmaco/${id}`)
  }

  const apriRicercaRecente = (ricerca: RicercaRecente) => {
    aggiungiRicercaRecente(ricerca)
    router.push(`/farmaco/${ricerca.id}`)
  }

  return (
    <div className="min-h-screen bg-[#fbfcfe]">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-2xl items-center justify-between gap-3 px-4 py-3">
          <p className="text-sm font-semibold tracking-wider text-slate-900">
            FARMACO<span className="text-blue-600">CHIARO</span>
          </p>
          <p className="text-right text-[10px] uppercase tracking-wider text-slate-500">
            Fogli illustrativi AIFA
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-6">
        <div className="border-l-2 border-blue-600 pl-3">
          <h1 className="text-lg font-semibold text-slate-900">
            Il foglio illustrativo, spiegato in modo facile da leggere
          </h1>
        </div>

        <div className="mt-5">
          <SearchBar
            onSelect={apriFarmaco}
            placeholder="Cerca farmaco, principio attivo o sintomo…"
          />
        </div>

        <div className="mx-auto mt-3">
          <div className="flex items-center gap-2 border border-gray-200 border-l-[3px] border-l-blue-600 bg-gray-50 p-3">
            <IconaBookOpen size={15} className="shrink-0 text-blue-600" />
            <p className="text-sm text-gray-700">
              <strong className="font-semibold text-gray-900">
                {TOTALE_FARMACI} farmaci
              </strong>{" "}
              già spiegati in modo semplice, con le fonti AIFA verificate.
            </p>
          </div>
          <p className="mt-2 flex items-center gap-1 text-[10px] text-gray-500">
            <IconaInfo size={11} className="shrink-0" />
            Il catalogo è in aggiornamento: nuovi farmaci vengono aggiunti man
            mano.
          </p>
        </div>

        <p className="mt-6 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Più consultati
        </p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
          {FARMACI_COMUNI.map((farmaco) => (
            <button
              key={farmaco.id}
              type="button"
              onClick={() => apriFarmaco(farmaco.id)}
              className="rounded-sm border-b border-blue-600 pb-0.5 text-sm text-blue-800 transition-colors hover:border-blue-800 hover:text-blue-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {farmaco.nome}
            </button>
          ))}
        </div>

        {ricercheRecenti.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-1 text-xs text-slate-500">
            <IconaInfo size={12} className="shrink-0 text-slate-400" />
            <span>Le tue ricerche recenti:</span>
            {ricercheRecenti.map((ricerca, indice) => (
              <span key={ricerca.id} className="inline-flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => apriRicercaRecente(ricerca)}
                  title={`Apri ${ricerca.nome}`}
                  className="rounded-sm font-semibold text-slate-700 underline decoration-slate-300 underline-offset-2 hover:text-blue-800 hover:decoration-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {ricerca.nome}
                </button>
                {indice < ricercheRecenti.length - 1 && (
                  <span aria-hidden="true">·</span>
                )}
              </span>
            ))}
            <span className="text-slate-500">(solo sul tuo dispositivo)</span>
            <button
              type="button"
              onClick={cancellaRicercheRecenti}
              aria-label="Cancella le ricerche recenti"
              title="Cancella le ricerche recenti"
              className="rounded p-1 text-slate-400 transition-colors hover:bg-gray-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <IconaX size={16} />
            </button>
          </div>
        )}

        <ul className="mt-8 grid grid-cols-3 border-t border-gray-200">
          {FUNZIONI.map((funzione) => {
            const Icona = funzione.icona
            return (
              <li
                key={funzione.titolo}
                className="border-r border-gray-200 px-2.5 py-3 last:border-r-0"
              >
                <Icona size={16} className={funzione.coloreIcona} />
                <p className="mt-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-900">
                  {funzione.titolo}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {funzione.descrizione}
                </p>
              </li>
            )
          })}
        </ul>
      </main>

      <footer className="mx-auto max-w-2xl px-4 pb-8">
        <p className="text-xs text-slate-500">
          Fonte ufficiale: fogli illustrativi AIFA · Non sostituisce il parere
          del medico o del farmacista
        </p>
      </footer>
    </div>
  )
}
