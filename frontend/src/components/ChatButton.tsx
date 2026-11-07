"use client"

export function ChatButton({
  isOpen,
  onToggle,
}: {
  isOpen: boolean
  onToggle: () => void
}) {
  return (
    <button
      onClick={onToggle}
      aria-expanded={isOpen}
      className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      {isOpen ? "Nascondi chatbot" : "Chiedi al chatbot"}
    </button>
  )
}
