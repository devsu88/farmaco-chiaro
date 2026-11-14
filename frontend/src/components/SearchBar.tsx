"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { api, type SearchResult } from "@/lib/api"

interface SearchBarProps {
  onSelect: (farmacoId: string) => void
  placeholder?: string
}

type StatoRicerca = "idle" | "loading" | "risultati" | "vuoto" | "errore"

export function SearchBar({ onSelect, placeholder = "Cerca un farmaco..." }: SearchBarProps) {
  const [query, setQuery] = useState("")
  const [risultati, setRisultati] = useState<SearchResult[]>([])
  const [stato, setStato] = useState<StatoRicerca>("idle")
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  // Ignora le risposte delle ricerche superate: senza questo, una risposta
  // lenta può riaprire il menu dopo che l'utente ha svuotato il campo.
  const runIdRef = useRef(0)

  const chiudi = useCallback(() => {
    runIdRef.current += 1
    setRisultati([])
    setIsOpen(false)
    setStato("idle")
  }, [])

  const cerca = useCallback(async (q: string) => {
    const runId = ++runIdRef.current
    if (!q.trim()) {
      setRisultati([])
      setIsOpen(false)
      setStato("idle")
      return
    }
    setStato("loading")
    try {
      const res = await api.search(q)
      if (runId !== runIdRef.current) return
      setRisultati(res.risultati)
      setStato(res.risultati.length > 0 ? "risultati" : "vuoto")
      // Anche zero risultati meritano il dropdown: spieghiamo cosa fare.
      setIsOpen(true)
    } catch (err) {
      if (runId !== runIdRef.current) return
      console.error("Errore ricerca:", err)
      setRisultati([])
      setStato("errore")
      setIsOpen(true)
    }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => cerca(query), 150)
    return () => clearTimeout(timer)
  }, [query, cerca])

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false)
        inputRef.current?.blur()
      }
    }

    document.addEventListener("pointerdown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("pointerdown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [])

  const cambiaQuery = (valore: string) => {
    setQuery(valore)
    if (!valore.trim()) chiudi()
  }

  const reset = () => {
    chiudi()
    setQuery("")
    inputRef.current?.focus()
  }

  const haRisultati = risultati.length > 0
  const mostraMessaggio = stato === "vuoto" || stato === "errore"
  const listaAperta = isOpen && (haRisultati || mostraMessaggio)

  return (
    <div ref={containerRef} className="relative w-full max-w-2xl">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => cambiaQuery(e.target.value)}
          placeholder={placeholder}
          role="combobox"
          aria-label="Cerca un farmaco"
          aria-autocomplete="list"
          aria-controls="risultati-ricerca"
          aria-expanded={listaAperta}
          className={`w-full py-3 pl-11 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all bg-white ${
            query ? "pr-20" : "pr-4"
          }`}
          onFocus={() => setIsOpen(haRisultati || mostraMessaggio)}
        />
        <svg
          className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>

        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {stato === "loading" && (
            <svg
              className="w-5 h-5 text-blue-500 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          )}
          {query && (
            <button
              type="button"
              onClick={reset}
              aria-label="Cancella la ricerca"
              title="Cancella la ricerca"
              className="p-1 rounded-full text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {listaAperta && (
        <div
          id="risultati-ricerca"
          role={haRisultati ? "listbox" : undefined}
          className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-y-auto"
        >
          {haRisultati ? (
            risultati.map((r) => (
              <button
                key={r.id}
                role="option"
                aria-selected={false}
                onClick={() => {
                  onSelect(r.id)
                  setQuery("")
                  chiudi()
                }}
                className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-0"
              >
                <div className="font-medium text-gray-900">{r.nome}</div>
                <div className="text-xs text-gray-500">
                  {r.principio_attivo} — {r.motivo}
                </div>
              </button>
            ))
          ) : stato === "errore" ? (
            <p role="alert" className="p-4 text-sm text-red-700">
              La ricerca non è al momento disponibile. Controlla la connessione e riprova.
            </p>
          ) : (
            <p role="status" className="p-4 text-sm text-gray-700">
              Non ho trovato «{query.trim()}». Prova con il principio attivo (es. paracetamolo invece di Tylenol).
            </p>
          )}
        </div>
      )}
    </div>
  )
}
