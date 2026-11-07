"use client"

import { useState, useEffect, useCallback } from "react"
import { api, type SearchResult } from "@/lib/api"

interface SearchBarProps {
  onSelect: (farmacoId: string) => void
  placeholder?: string
}

export function SearchBar({ onSelect, placeholder = "Cerca un farmaco..." }: SearchBarProps) {
  const [query, setQuery] = useState("")
  const [risultati, setRisultati] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)

  const cerca = useCallback(async (q: string) => {
    if (!q.trim()) {
      setRisultati([])
      setIsOpen(false)
      return
    }
    setLoading(true)
    try {
      const res = await api.search(q)
      setRisultati(res.risultati)
      setIsOpen(res.risultati.length > 0)
    } catch (err) {
      console.error("Errore ricerca:", err)
      setRisultati([])
      setIsOpen(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => cerca(query), 150)
    return () => clearTimeout(timer)
  }, [query, cerca])

  return (
    <div className="relative w-full max-w-2xl">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          aria-label="Cerca un farmaco"
          aria-controls="risultati-ricerca"
          className="w-full px-4 py-3 pl-11 pr-4 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all bg-white"
          onFocus={() => setIsOpen(risultati.length > 0)}
        />
        <svg
          className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        {loading && (
          <svg
            className="w-5 h-5 text-blue-500 animate-spin absolute right-3 top-1/2 -translate-y-1/2"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
      </div>

      {isOpen && risultati.length > 0 && (
        <div
          id="risultati-ricerca"
          role="listbox"
          className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto"
        >
          {risultati.map((r) => (
            <button
              key={r.id}
              role="option"
              aria-selected={false}
              onClick={() => {
                onSelect(r.id)
                setQuery("")
                setRisultati([])
                setIsOpen(false)
              }}
              className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-0"
            >
              <div className="font-medium text-gray-900">{r.nome}</div>
              <div className="text-xs text-gray-500">
                {r.principio_attivo} — {r.motivo}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}