import { NextResponse } from "next/server"

export const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000"

const rawTimeout = Number(process.env.PROXY_TIMEOUT_MS ?? "100000")
export const PROXY_TIMEOUT_MS =
  Number.isFinite(rawTimeout) && rawTimeout > 0 ? rawTimeout : 100000

/**
 * Prepara la chiamata al backend: timeout, same-origin e IP del browser.
 * X-Forwarded-For serve al rate limit del backend: senza, il backend vedrebbe
 * solo l'IP del server Next e il limite diventerebbe globale.
 */
function buildInit(init?: RequestInit, request?: Request): RequestInit {
  const headers = new Headers(init?.headers)
  const forwarded =
    request?.headers.get("x-forwarded-for") ??
    request?.headers.get("x-real-ip")

  if (forwarded) headers.set("x-forwarded-for", forwarded)

  return {
    ...init,
    headers,
    cache: "no-store",
    signal: init?.signal ?? AbortSignal.timeout(PROXY_TIMEOUT_MS),
  }
}

function isTimeout(error: unknown): boolean {
  return (
    error instanceof Error &&
    (error.name === "TimeoutError" || error.name === "AbortError")
  )
}

function timeoutResponse(): NextResponse {
  return NextResponse.json(
    {
      error: {
        code: "BACKEND_TIMEOUT",
        message: "Il servizio sta impiegando troppo tempo. Riprova.",
      },
    },
    { status: 504 }
  )
}

function backendUnavailable(): NextResponse {
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

function passthroughHeaders(
  res: Response,
  fallbackContentType: string
): Record<string, string> {
  const headers: Record<string, string> = {
    "content-type": res.headers.get("content-type") || fallbackContentType,
  }
  for (const name of ["retry-after", "x-request-id"]) {
    const value = res.headers.get(name)
    if (value) headers[name] = value
  }
  return headers
}

/**
 * Inoltra una richiesta al backend FastAPI mantenendo il browser same-origin.
 * Gli errori di rete diventano un 502 JSON, i timeout un 504, senza esporre
 * dettagli interni.
 */
export async function proxyAudio(
  path: string,
  init?: RequestInit,
  request?: Request
): Promise<NextResponse> {
  try {
    const res = await fetch(`${BACKEND_URL}${path}`, buildInit(init, request))
    const headers = passthroughHeaders(res, "audio/wav")

    if (!res.ok) {
      return new NextResponse(await res.text(), {
        status: res.status,
        headers,
      })
    }

    // Passiamo il body in streaming: l'audio non viene bufferizzato in memoria
    // dal server Next e le risposte lunghe non bloccano le richieste successive.
    headers["cache-control"] =
      res.headers.get("cache-control") || "private, max-age=3600"
    return new NextResponse(res.body, { status: res.status, headers })
  } catch (error) {
    return isTimeout(error) ? timeoutResponse() : backendUnavailable()
  }
}

export async function proxyToBackend(
  path: string,
  init?: RequestInit,
  request?: Request
): Promise<NextResponse> {
  try {
    const res = await fetch(`${BACKEND_URL}${path}`, buildInit(init, request))
    const body = await res.text()
    return new NextResponse(body, {
      status: res.status,
      headers: passthroughHeaders(res, "application/json"),
    })
  } catch (error) {
    return isTimeout(error) ? timeoutResponse() : backendUnavailable()
  }
}
