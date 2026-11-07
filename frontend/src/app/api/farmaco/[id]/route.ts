import { proxyToBackend } from "@/lib/backend"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return proxyToBackend(`/api/farmaci/${encodeURIComponent(id)}`)
}
