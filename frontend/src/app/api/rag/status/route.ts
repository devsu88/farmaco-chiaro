import { proxyToBackend } from "@/lib/backend"

/** Stato del RAG: conteggi, modalità di retrieval e disponibilità Qdrant. */
export async function GET() {
  return proxyToBackend("/api/rag/status")
}
