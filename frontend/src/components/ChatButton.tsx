"use client"

import { useState } from "react"
import { ChatPopup } from "@/components/ChatPopup"
import type { FonteCitata } from "@/lib/api"

export function ChatButton({
  farmacoId,
  onHighlightSource,
}: {
  farmacoId: string
  onHighlightSource?: (fonte: FonteCitata) => void
}) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div>
      <button
        onClick={() => setIsOpen(true)}
        className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        Chiedi al chatbot
      </button>
      <ChatPopup
        farmacoId={farmacoId}
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        onHighlightSource={onHighlightSource}
      />
    </div>
  )
}
