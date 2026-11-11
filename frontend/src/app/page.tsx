"use client"

import { useRouter } from "next/navigation"
import { SearchBar } from "@/components/SearchBar"

export default function Home() {
  const router = useRouter()

  const selezionaFarmaco = (id: string) => {
    router.push(`/farmaco/${id}`)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">Farmaco Chiaro</h1>
          <p className="mt-1 text-gray-600">
            Fogli illustrativi AIFA in linguaggio facile da leggere
          </p>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-16">
        <div className="mb-10 text-center">
          <p className="text-lg text-gray-700 mb-6">
            Cerca un farmaco per nome, principio attivo o sintomo
          </p>
          <SearchBar
            onSelect={selezionaFarmaco}
            placeholder="Es. Tachipirina, paracetamolo, mal di testa..."
          />
        </div>

        <div className="p-6 bg-blue-50 rounded-xl border border-blue-100">
          <h2 className="font-semibold text-blue-900 mb-2">Come funziona</h2>
          <ul className="list-disc list-inside text-sm text-blue-800 space-y-1">
            <li>Cerca il farmaco che ti interessa</li>
            <li>Vedi il foglio illustrativo originale e la versione semplificata</li>
            <li>Fai domande al chatbot: ogni risposta cita il paragrafo del foglio</li>
            <li>Ascolta la versione semplificata con il pulsante «Ascolta»</li>
          </ul>
        </div>
      </main>
    </div>
  )
}
