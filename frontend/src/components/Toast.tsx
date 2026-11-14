"use client"

import { useEffect, useRef, useState } from "react"

interface ToastProps {
  messaggio: string
  onChiuso: () => void
}

const DURATA_MS = 3000

export function Toast({ messaggio, onChiuso }: ToastProps) {
  const [visibile, setVisibile] = useState(false)
  // Il timer non deve ripartire quando il genitore si ri-renderizza con una
  // nuova funzione: leggiamo sempre l'ultima `onChiuso` da un ref.
  const onChiusoRef = useRef(onChiuso)

  useEffect(() => {
    onChiusoRef.current = onChiuso
  }, [onChiuso])

  // Montato a opacity-0: il frame successivo attiva il fade-in.
  useEffect(() => {
    const frame = requestAnimationFrame(() => setVisibile(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => onChiusoRef.current(), DURATA_MS)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div
      role="status"
      className={`fixed bottom-4 left-1/2 z-40 -translate-x-1/2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm text-white shadow-lg transition-opacity duration-200 ${
        visibile ? "opacity-100" : "opacity-0"
      }`}
    >
      {messaggio}
    </div>
  )
}
