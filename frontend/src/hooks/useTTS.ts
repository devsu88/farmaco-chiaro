"use client"

import { useCallback, useEffect, useRef, useState } from "react"

export function useTTS() {
  const [speaking, setSpeaking] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const urlRef = useRef<string | null>(null)

  const stop = useCallback(() => {
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

  const speak = useCallback(
    async (text: string) => {
      if (!text.trim()) return

      stop()
      setError(null)
      setLoading(true)

      try {
        const res = await fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ testo: text }),
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
        const url = URL.createObjectURL(blob)
        urlRef.current = url

        const audio = new Audio(url)
        audioRef.current = audio
        audio.onended = () => {
          setSpeaking(false)
          if (urlRef.current === url) {
            URL.revokeObjectURL(url)
            urlRef.current = null
          }
        }
        audio.onerror = () => {
          setSpeaking(false)
          setError("Impossibile riprodurre l'audio generato.")
        }

        setSpeaking(true)
        await audio.play()
      } catch (err) {
        setSpeaking(false)
        setError(
          err instanceof Error
            ? err.message
            : "Sintesi vocale non disponibile"
        )
      } finally {
        setLoading(false)
      }
    },
    [stop]
  )

  return { speak, stop, speaking, loading, error }
}
