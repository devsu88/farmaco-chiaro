import { proxyToBackend } from "@/lib/backend"

export async function POST(request: Request) {
  const body = await request.json()
  return proxyToBackend("/api/simplify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}
