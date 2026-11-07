import { proxyToBackend } from "@/lib/backend"

export async function POST(request: Request) {
  const body = await request.json()
  return proxyToBackend("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}
