"use client"

import { useEffect, useRef, useState } from "react"
import { api, type FonteCitata } from "@/lib/api"

interface ChatPopupProps {
  farmacoId: string
  isOpen: boolean
  onClose: () => void
  onHighlightSource?: (fonte: FonteCitata) => void
}

export function ChatPopup({
  farmacoId,
  isOpen,
  onClose,
  onHighlightSource,
}: ChatPopupProps) {
  const [input, setInput] = useState("")
  const [messaggi, setMessaggi] = useState<
    { ruolo: "utente" | "assistente"; testo: string }[]
  >([])
  const [loading, setLoading] = useState(false)
  const [sessioneId, setSessioneId] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messaggi, loading])

  useEffect(() => {
    if (!isOpen) return
    inputRef.current?.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [isOpen, onClose])

  const invia = async () => {
    const testo = input.trim()
    if (!testo || loading) return

    const storico = messaggi.map((m) => ({ ruolo: m.ruolo, testo: m.testo }))
    setMessaggi((prev) => [...prev, { ruolo: "utente", testo }])
    setInput("")
    setLoading(true)

    try {
      const res = await api.chat({
        farmaco_id: farmacoId,
        messaggio: testo,
        storico,
        sessione_id: sessioneId ?? undefined,
      })

      if (res.sessione_id) setSessioneId(res.sessione_id)
      setMessaggi((prev) => [
        ...prev,
        { ruolo: "assistente", testo: res.risposta },
      ])

      if (res.fonti.length > 0) {
        onHighlightSource?.(res.fonti[0])
      }
    } catch (error) {
      console.error("Errore chat:", error)
      setMessaggi((prev) => [
        ...prev,
        {
          ruolo: "assistente",
          testo: "Scusa, c'è stato un errore. Riprova tra poco.",
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="chat-title"
        className="relative w-full max-w-md max-h-[80vh] bg-white rounded-2xl shadow-2xl flex flex-col border border-gray-100"
      >
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 id="chat-title" className="font-semibold text-gray-900">
              Chatbot Farmaco
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Risponde citando il foglio illustrativo
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Chiudi chat"
            className="p-2 text-gray-500 hover:text-gray-700 rounded hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div
          className="flex-1 overflow-y-auto p-4 space-y-4"
          aria-live="polite"
          aria-relevant="additions"
        >
          {messaggi.length === 0 && (
            <p className="text-sm text-gray-500">
              Fai una domanda sul farmaco. La risposta citerà il punto esatto del
              foglio illustrativo.
            </p>
          )}

          {messaggi.map((m, i) => (
            <div
              key={i}
              className={`flex gap-3 max-w-[85%] ${
                m.ruolo === "utente" ? "flex-row-reverse ml-auto" : "ml-0"
              }`}
            >
              <div
                className={`px-3 py-2 rounded-lg text-sm ${
                  m.ruolo === "utente"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-800"
                }`}
              >
                {m.testo}
              </div>
            </div>
          ))}

          {loading && (
            <div className="ml-0 flex gap-3">
              <div className="bg-gray-100 text-gray-800 px-3 py-2 rounded-lg text-sm animate-pulse">
                Sto cercando nel foglio illustrativo...
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="p-3 border-t border-gray-100 bg-white">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && invia()}
              placeholder="Scrivi una domanda sul farmaco..."
              aria-label="Domanda sul farmaco"
              className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              disabled={loading}
            />
            <button
              onClick={invia}
              disabled={loading || !input.trim()}
              className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg disabled:bg-gray-300 hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Invia
            </button>
          </div>
          <p className="text-[11px] text-gray-400 mt-2 text-center">
            Non sostituisce il medico o il farmacista.
          </p>
          {sessioneId && (
            <p className="text-[10px] text-gray-300 mt-1 text-center">
              Sessione: {sessioneId.slice(0, 8)}...
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
