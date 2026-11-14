"use client"

import { useSyncExternalStore } from "react"
import { useRouter } from "next/navigation"
import { SearchBar } from "@/components/SearchBar"
import { api } from "@/lib/api"
import { FARMACI_COMUNI } from "@/lib/farmaci-comuni"
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
    emoji: "📖",
    titolo: "Trova il farmaco",
    descrizione: "Ricerca per nome o sintomo",
  },
  {
    emoji: "✅",
    titolo: "Leggi la versione facile",
    descrizione: "Solo l'essenziale, già verificato",
  },
  {
    emoji: "🔊",
    titolo: "Ascolta o chiedi",
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
    <div className="min-h-screen bg-slate-50">
      <header className="bg-gradient-to-br from-blue-100 to-sky-100">
        <div className="mx-auto max-w-2xl px-4 py-8 text-center">
          <p className="text-3xl leading-none" aria-hidden="true">
            💊
          </p>
          <h1 className="mt-2 text-2xl font-bold text-sky-900">Farmaco Chiaro</h1>
          <p className="mt-1 text-sm text-sky-700">
            Il foglio illustrativo, spiegato in modo facile da leggere
          </p>

          <div className="mx-auto mt-5 w-full max-w-md">
            <SearchBar
              onSelect={apriFarmaco}
              placeholder="Cerca farmaco, principio attivo o sintomo…"
            />
          </div>

          <p className="mt-4 text-xs text-slate-600">Più cercati questa settimana:</p>
          <div className="mt-1.5 flex flex-wrap justify-center gap-1.5">
            {FARMACI_COMUNI.map((farmaco) => (
              <button
                key={farmaco.id}
                type="button"
                onClick={() => apriFarmaco(farmaco.id)}
                className="rounded-full border border-blue-300 bg-white px-3 py-1 text-sm text-blue-700 transition-colors hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {farmaco.nome}
              </button>
            ))}
          </div>

          {ricercheRecenti.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center justify-center gap-1 text-xs text-slate-500">
              <span>Le tue ricerche recenti:</span>
              {ricercheRecenti.map((ricerca, indice) => (
                <span key={ricerca.id} className="inline-flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => apriRicercaRecente(ricerca)}
                    title={`Apri ${ricerca.nome}`}
                    className="rounded font-semibold text-slate-700 hover:text-blue-700 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {ricerca.nome}
                  </button>
                  {indice < ricercheRecenti.length - 1 && (
                    <span aria-hidden="true">·</span>
                  )}
                </span>
              ))}
              <span className="text-slate-400">(solo sul tuo dispositivo)</span>
              <button
                type="button"
                onClick={cancellaRicercheRecenti}
                aria-label="Cancella le ricerche recenti"
                title="Cancella le ricerche recenti"
                className="rounded p-1 text-slate-400 transition-colors hover:bg-white/70 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-4">
        <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
          {FUNZIONI.map((funzione) => (
            <li
              key={funzione.titolo}
              className="rounded-xl border border-slate-200 bg-white px-2 py-3 text-center"
            >
              <p className="text-xl leading-none" aria-hidden="true">
                {funzione.emoji}
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-700">
                {funzione.titolo}
              </p>
              <p className="text-xs text-slate-500">{funzione.descrizione}</p>
            </li>
          ))}
        </ul>
      </main>
    </div>
  )
}
