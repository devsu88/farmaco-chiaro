import { proxyAudio } from "@/lib/backend"

export async function POST(request: Request) {
  const body = await request.json()
  return proxyAudio("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}
