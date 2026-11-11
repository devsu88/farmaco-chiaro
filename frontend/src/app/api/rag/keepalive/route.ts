import { proxyToBackend } from "@/lib/backend"

/**
 * Keepalive del cluster Qdrant: il cron Vercel chiama questa route ogni
 * giorno, così il free tier non sospende la collezione per inattività.
 */
export async function GET() {
  return proxyToBackend("/api/rag/keepalive")
}
