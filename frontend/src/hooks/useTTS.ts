"use client"

import { useCallback, useEffect, useRef, useState } from "react"

const MAX_CHUNK_CHARS = 600

function dividiInChunk(testo: string, maxChars = MAX_CHUNK_CHARS): string[] {
  const frasi = testo.match(/[^.!?]+[.!?]*/g) ?? [testo]
  const chunk: string[] = []
  let corrente = ""

  for (const frase of frasi) {
    const parti =
      frase.length > maxChars
        ? (frase.match(new RegExp(`.{1,${maxChars}}`, "g")) ?? [frase])
        : [frase]

    for (const parte of parti) {
      const candidato = `${corrente} ${parte}`.trim()
      if (candidato.length > maxChars && corrente) {
        chunk.push(corrente)
        corrente = parte.trim()
      } else {
        corrente = candidato
      }
    }
  }
  if (corrente) chunk.push(corrente)
  return chunk.length > 0 ? chunk : [testo]
}

function attesa(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// `onPronto` scatta una volta per `speak`, quando la riproduzione parte
// davvero: è il segnale che l'audio è pronto (l'errore non lo produce).
export function useTTS(onPronto?: () => void) {
  const [speaking, setSpeaking] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const urlRef = useRef<string | null>(null)
  const runIdRef = useRef(0)
  const resolvePlaybackRef = useRef<(() => void) | null>(null)

  const stop = useCallback(() => {
    runIdRef.current += 1

    if (resolvePlaybackRef.current) {
      resolvePlaybackRef.current()
      resolvePlaybackRef.current = null
    }
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      audioRef.current = null
    }
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current)
      urlRef.current = null
    }
    setSpeaking(false)
    setLoading(false)
  }, [])

  useEffect(() => {
    return () => stop()
  }, [stop])

  const riproduciChunk = useCallback(
    async (
      testo: string,
      runId: number,
      onProntoChunk?: () => void
    ): Promise<void> => {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ testo }),
      })

      if (!res.ok) {
        let messaggio = "Sintesi vocale non disponibile"
        try {
          const body = await res.json()
          messaggio = body?.detail || body?.error?.message || messaggio
        } catch {
          // risposta non JSON
        }
        throw new Error(messaggio)
      }

      const blob = await res.blob()
      if (runId !== runIdRef.current) return

      const url = URL.createObjectURL(blob)
      urlRef.current = url

      const audio = new Audio(url)
      audioRef.current = audio

      await new Promise<void>((resolve) => {
        resolvePlaybackRef.current = resolve
        audio.onended = () => resolve()
        audio.onerror = () => resolve()
        audio
          .play()
          .then(() => {
            setSpeaking(true)
            setLoading(false)
            onProntoChunk?.()
          })
          .catch(() => {
            setError("Il browser ha bloccato la riproduzione audio.")
            resolve()
          })
      })

      resolvePlaybackRef.current = null
      if (urlRef.current === url) {
        URL.revokeObjectURL(url)
        urlRef.current = null
      }
    },
    []
  )

  const speak = useCallback(
    async (text: string) => {
      if (!text.trim()) return

      stop()
      const runId = runIdRef.current
      setError(null)
      setLoading(true)

      try {
        const chunks = dividiInChunk(text)

        // Il primo chunk che parte avvisa una sola volta, anche quando il
        // testo è spezzato in più richieste.
        let notificato = false
        const onProntoChunk = onPronto
          ? () => {
              if (notificato) return
              notificato = true
              onPronto()
            }
          : undefined

        for (const chunk of chunks) {
          if (runId !== runIdRef.current) return
          await riproduciChunk(chunk, runId, onProntoChunk)
          if (runId !== runIdRef.current) return
          await attesa(120)
        }
      } catch (err) {
        setSpeaking(false)
        setError(
          err instanceof Error
            ? err.message
            : "Sintesi vocale non disponibile"
        )
      } finally {
        setLoading(false)
        if (runId === runIdRef.current) {
          setSpeaking(false)
        }
      }
    },
    [riproduciChunk, stop, onPronto]
  )

  return { speak, stop, speaking, loading, error }
}
