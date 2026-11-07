import { NextResponse } from "next/server"

export const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000"

/**
 * Inoltra una richiesta al backend FastAPI mantenendo il browser same-origin.
 * Gli errori di rete diventano un 502 JSON, senza esporre dettagli interni.
 */
export async function proxyToBackend(
  path: string,
  init?: RequestInit
): Promise<NextResponse> {
  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      cache: "no-store",
      ...init,
    })

    const body = await res.text()
    const contentType = res.headers.get("content-type") || "application/json"
    return new NextResponse(body, {
      status: res.status,
      headers: { "content-type": contentType },
    })
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "BACKEND_UNAVAILABLE",
          message: "Backend non disponibile",
        },
      },
      { status: 502 }
    )
  }
}
