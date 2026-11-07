"use client"

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react"

const subscribe = () => () => {}

export function useSpeech() {
  const supported = useSyncExternalStore(
    subscribe,
    () => "speechSynthesis" in window,
    () => false
  )
  const [speaking, setSpeaking] = useState(false)
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const [error, setError] = useState<string | null>(null)
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!supported) return

    const loadVoices = () => {
      const disponibili = window.speechSynthesis.getVoices()
      if (disponibili.length > 0) setVoices(disponibili)
    }

    loadVoices()
    window.speechSynthesis.addEventListener("voiceschanged", loadVoices)

    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", loadVoices)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      window.speechSynthesis.cancel()
    }
  }, [supported])

  const stop = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel()
    }
    setSpeaking(false)
  }, [])

  const speak = useCallback(
    (text: string) => {
      if (!supported || !text.trim()) return

      setError(null)
      window.speechSynthesis.cancel()

      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = "it-IT"
      utterance.rate = 0.9
      utterance.pitch = 1
      utterance.volume = 1

      const voceItaliana = voices.find((voce) =>
        voce.lang.toLowerCase().startsWith("it")
      )
      if (voceItaliana) utterance.voice = voceItaliana

      utterance.onstart = () => setSpeaking(true)
      utterance.onend = () => setSpeaking(false)
      utterance.onerror = (event) => {
        setSpeaking(false)
        const codice = event.error || "unknown"
        setError(
          codice === "not-allowed"
            ? "Il browser ha bloccato la sintesi vocale. Riprova dopo aver interagito con la pagina."
            : "La sintesi vocale non è disponibile in questo browser o non ha voci installate."
        )
      }

      utteranceRef.current = utterance
      setSpeaking(true)

      // Su Chrome il cancel immediato prima di speak può annullare la lettura.
      timeoutRef.current = setTimeout(() => {
        window.speechSynthesis.resume()
        window.speechSynthesis.speak(utterance)
      }, 60)
    },
    [supported, voices]
  )

  return {
    speak,
    stop,
    speaking,
    supported,
    error,
    voices,
    utteranceRef,
  }
}
