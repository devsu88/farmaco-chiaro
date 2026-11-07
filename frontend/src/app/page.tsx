"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState, useEffect } from "react"
import { api, type FarmacoPreview } from "@/lib/api"
import { SearchBar } from "@/components/SearchBar"

export default function Home() {
  const router = useRouter()
  const [farmaci, setFarmaci] = useState<FarmacoPreview[]>([])
  const [loading, setLoading] = useState(true)

  const selezionaFarmaco = (id: string) => {
    router.push(`/farmaco/${id}`)
  }

  useEffect(() => {
    api.listFarmaci()
      .then((data) => {
        setFarmaci(data)
        setLoading(false)
      })
      .catch((err) => {
        console.error("Errore caricamento farmaci:", err)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
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

      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-8">
          <p className="text-lg text-gray-700 mb-4">
            Cerca un farmaco per nome, principio attivo o sintomo
          </p>
          <SearchBar onSelect={selezionaFarmaco} placeholder="Es. Tachipirina, paracetamolo, mal di testa..." />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {farmaci.map((f) => (
            <Link
              key={f.id}
              href={`/farmaco/${f.id}`}
              className="group block bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md hover:border-blue-300 transition-all cursor-pointer"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center text-blue-600 font-bold">
                  {f.id.charAt(0).toUpperCase()}
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 group-hover:text-blue-600">{f.nome}</h3>
                  <p className="text-xs text-gray-500 mt-1">{f.principio_attivo}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>

        <div className="mt-8 p-6 bg-blue-50 rounded-xl border border-blue-100">
          <h3 className="font-semibold text-blue-900 mb-2">Come funziona</h3>
          <ul className="list-disc list-inside text-sm text-blue-800 space-y-1">
            <li>Cerca un farmaco dalla lista o usa la ricerca sopra</li>
            <li>Vedi il foglio illustrativo originale a sinistra e la versione semplificata a destra</li>
            <li>Usa il chatbot per fare domande sul farmaco con citazioni dal foglio</li>
            <li>Ascolta la versione semplificata con il pulsante «Ascolta»</li>
          </ul>
        </div>
      </main>
    </div>
  )
}