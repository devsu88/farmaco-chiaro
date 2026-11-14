"use client"

import { useEffect, useRef, useState } from "react"
import { api, type FonteCitata } from "@/lib/api"

interface ChatPanelProps {
  farmacoId: string
  isOpen: boolean
  onClose: () => void
  onHighlightSource?: (fonte: FonteCitata) => void
}

export function ChatPanel({
  farmacoId,
  isOpen,
  onClose,
  onHighlightSource,
}: ChatPanelProps) {
  const [input, setInput] = useState("")
  const [messaggi, setMessaggi] = useState<
    { ruolo: "utente" | "assistente"; testo: string; fonti?: FonteCitata[] }[]
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
        { ruolo: "assistente", testo: res.risposta, fonti: res.fonti },
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
    <section
      aria-label="Chatbot farmaco"
      className="bg-white border border-gray-200 rounded-lg shadow-sm flex flex-col h-[65vh] lg:h-[calc(100vh-9rem)] lg:sticky lg:top-24"
    >
      <div className="border-t-2 border-t-blue-600 p-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-blue-900">Chatbot Farmaco</h2>
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
            foglio illustrativo, evidenziato qui a fianco.
          </p>
        )}

        {messaggi.map((m, i) => (
          <div
            key={i}
            className={`flex flex-col gap-1 max-w-[92%] ${
              m.ruolo === "utente" ? "ml-auto items-end" : "mr-auto items-start"
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
            {m.ruolo === "assistente" && m.fonti && m.fonti.length > 0 && (
              <div className="flex flex-col gap-1">
                {m.fonti.map((fonte, indice) => (
                  <button
                    key={`${fonte.blocco_id ?? "fonte"}-${indice}`}
                    onClick={() => onHighlightSource?.(fonte)}
                    title={fonte.testo_evidenziato.slice(0, 160)}
                    className="text-left text-[11px] text-blue-700 hover:underline"
                  >
                    Vai alla fonte {indice + 1}: {fonte.sezione}
                    {fonte.paragrafo ? `, ${fonte.paragrafo}` : ""}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="mr-auto">
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
    </section>
  )
}
