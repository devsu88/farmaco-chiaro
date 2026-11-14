"use client"

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react"
import {
  IconaCompass,
  IconaMessage,
  IconaMore,
  IconaRefresh,
  IconaShare,
} from "./Icone"

interface PiuMenuProps {
  chatAperta: boolean
  onApriChat: () => void
  onApriScenario: () => void
  onCondividi: () => void
  onRigenera: () => void
}

const stileVoce =
  "flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-sm text-gray-700 transition-colors enabled:hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-gray-400 disabled:opacity-50 disabled:cursor-not-allowed"

export function PiuMenu({
  chatAperta,
  onApriChat,
  onApriScenario,
  onCondividi,
  onRigenera,
}: PiuMenuProps) {
  const [aperto, setAperto] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const chiudi = useCallback(() => setAperto(false), [])

  // Chiude su click esterno e su Escape, come la tendina della ricerca.
  useEffect(() => {
    if (!aperto) return

    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        chiudi()
      }
    }
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        chiudi()
        triggerRef.current?.focus()
      }
    }

    document.addEventListener("pointerdown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("pointerdown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [aperto, chiudi])

  // All'apertura il focus entra nella prima voce disponibile.
  useEffect(() => {
    if (!aperto) return
    menuRef.current
      ?.querySelector<HTMLButtonElement>('[role="menuitem"]:not([disabled])')
      ?.focus()
  }, [aperto])

  const vociDisponibili = () =>
    Array.from(
      menuRef.current?.querySelectorAll<HTMLButtonElement>(
        '[role="menuitem"]:not([disabled])'
      ) ?? []
    )

  const onKeyDownMenu = (event: KeyboardEvent<HTMLDivElement>) => {
    // Con role="menu" il Tab esce dal menu invece di attraversarlo.
    if (event.key === "Tab") {
      chiudi()
      return
    }

    const voci = vociDisponibili()
    if (voci.length === 0) return
    const corrente = voci.indexOf(document.activeElement as HTMLButtonElement)

    if (event.key === "ArrowDown") {
      event.preventDefault()
      voci[corrente < 0 ? 0 : (corrente + 1) % voci.length]?.focus()
    } else if (event.key === "ArrowUp") {
      event.preventDefault()
      voci[
        corrente < 0 ? voci.length - 1 : (corrente - 1 + voci.length) % voci.length
      ]?.focus()
    } else if (event.key === "Home") {
      event.preventDefault()
      voci[0]?.focus()
    } else if (event.key === "End") {
      event.preventDefault()
      voci[voci.length - 1]?.focus()
    }
  }

  // Dopo una voce il focus torna al trigger: se l'azione apre un pannello,
  // sarà il pannello a spostarlo dove serve.
  const esegui = (azione: () => void) => {
    azione()
    chiudi()
    triggerRef.current?.focus()
  }

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setAperto((prev) => !prev)}
        aria-label="Altre funzioni"
        aria-haspopup="menu"
        aria-expanded={aperto}
        className="p-2 rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400"
      >
        <IconaMore size={18} />
      </button>

      {aperto && (
        <div
          ref={menuRef}
          role="menu"
          aria-label="Altre funzioni"
          onKeyDown={onKeyDownMenu}
          className="absolute right-0 z-30 mt-2 w-64 rounded-md border border-gray-200 bg-white py-1 shadow-sm"
        >
          <button
            type="button"
            role="menuitem"
            disabled={chatAperta}
            aria-disabled={chatAperta ? true : undefined}
            onClick={() => esegui(onApriChat)}
            className={stileVoce}
          >
            <IconaMessage size={14} className="shrink-0 text-gray-400" />
            {chatAperta ? "Nascondi chatbot" : "Chiedi al chatbot"}
          </button>

          <button
            type="button"
            role="menuitem"
            onClick={() => esegui(onApriScenario)}
            className={stileVoce}
          >
            <IconaCompass size={14} className="shrink-0 text-gray-400" />
            Cosa faccio se…?
          </button>

          <button
            type="button"
            role="menuitem"
            onClick={() => esegui(onCondividi)}
            className={stileVoce}
          >
            <IconaShare size={14} className="shrink-0 text-gray-400" />
            Condividi
          </button>

          <button
            type="button"
            role="menuitem"
            onClick={() => esegui(onRigenera)}
            className={stileVoce}
          >
            <IconaRefresh size={14} className="shrink-0 text-gray-400" />
            Rigenera versione facile
          </button>
        </div>
      )}
    </div>
  )
}
