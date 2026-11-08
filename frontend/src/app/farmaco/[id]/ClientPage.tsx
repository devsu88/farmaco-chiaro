"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  api,
  type DocumentoResponse,
  type FarmacoDetail,
  type FonteCitata,
  type SimplifyResponse,
} from "@/lib/api"
import { OriginalDocument } from "@/components/OriginalDocument"
import { EasyText } from "@/components/EasyText"
import { ChatButton } from "@/components/ChatButton"
import { ChatPanel } from "@/components/ChatPanel"
import { ScenarioWizard } from "@/components/ScenarioWizard"
import { useTTS } from "@/hooks/useTTS"

export default function ClientPage({ farmacoId }: { farmacoId: string }) {
  const router = useRouter()
  const {
    speak,
    stop,
    speaking,
    loading: ttsLoading,
    error: ttsError,
  } = useTTS()

  const [farmaco, setFarmaco] = useState<FarmacoDetail | null>(null)
  const [documento, setDocumento] = useState<DocumentoResponse | null>(null)
  const [versioneFacile, setVersioneFacile] = useState<SimplifyResponse | null>(
    null
  )
  const [semplificando, setSemplificando] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [simplifyError, setSimplifyError] = useState<string | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [scenarioOpen, setScenarioOpen] = useState(false)
  const [fonteEvidenziata, setFonteEvidenziata] = useState<FonteCitata | null>(
    null
  )
  const [focusFonte, setFocusFonte] = useState(0)

  const evidenziaFonte = useCallback((fonte: FonteCitata) => {
    setFonteEvidenziata(fonte)
    setFocusFonte((valore) => valore + 1)
  }, [])

  useEffect(() => {
    let cancelled = false

    const carica = async () => {
      setLoading(true)
      setError(null)

      const [farmacoRes, documentoRes] = await Promise.allSettled([
        api.getFarmaco(farmacoId),
        api.getDocumento(farmacoId),
      ])

      if (cancelled) return

      if (farmacoRes.status === "rejected") {
        setError(
          farmacoRes.reason instanceof Error
            ? farmacoRes.reason.message
            : "Errore nel caricamento del farmaco"
        )
        setLoading(false)
        return
      }

      const farmacoCaricato = farmacoRes.value
      let documentoCaricato: DocumentoResponse | null =
        documentoRes.status === "fulfilled" ? documentoRes.value : null

      // Se il documento citabile non è disponibile, mostriamo il catalogo
      // come fallback: l'utente vede comunque il testo originale.
      if (!documentoCaricato) {
        documentoCaricato = {
          farmaco_id: farmacoCaricato.id,
          documento: `Farmaco ${farmacoCaricato.nome}`,
          sezioni: Object.entries(farmacoCaricato.sezioni).map(
            ([titolo, testo]) => ({
              titolo,
              blocchi: [
                {
                  blocco_id: `catalogo-${titolo}`,
                  paragrafo: "1",
                  testo,
                },
              ],
            })
          ),
        }
      }

      setFarmaco(farmacoCaricato)
      setDocumento(documentoCaricato)
      setLoading(false)

      // La modalità guidata e gli scenari possono aprire il foglio su un
      // blocco preciso passando ?fonte=<blocco_id>.
      const bloccoId = new URLSearchParams(window.location.search).get("fonte")
      if (bloccoId) {
        for (const sezione of documentoCaricato.sezioni) {
          const blocco = sezione.blocchi.find(
            (item) => item.blocco_id === bloccoId
          )
          if (!blocco) continue
          setFonteEvidenziata({
            blocco_id: blocco.blocco_id,
            documento: documentoCaricato.documento,
            sezione: sezione.titolo,
            paragrafo: blocco.paragrafo,
            testo_evidenziato: blocco.testo,
            verificata: true,
          })
          setFocusFonte((valore) => valore + 1)
          break
        }
      }
    }

    carica()
    return () => {
      cancelled = true
    }
  }, [farmacoId])

  const semplifica = useCallback(
    async (forza = false) => {
      if (semplificando) return
      setSemplificando(true)
      setSimplifyError(null)

      try {
        const versione = await api.simplify({
          farmaco_id: farmacoId,
          sezione: "tutta",
          forza,
        })
        setVersioneFacile(versione)
        setFonteEvidenziata(null)
      } catch (err) {
        setSimplifyError(
          err instanceof Error ? err.message : "Semplificazione non disponibile"
        )
      } finally {
        setSemplificando(false)
      }
    },
    [farmacoId, semplificando]
  )

  const testoDaLeggere = versioneFacile
    ? [versioneFacile.una_frase, ...versioneFacile.versione_facile].join(" ")
    : ""

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-8">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4" />
        <h2 className="text-lg font-medium text-gray-700">
          Caricamento in corso...
        </h2>
        <p className="text-sm text-gray-500 mt-1">
          Sto caricando il foglio illustrativo di {farmacoId}
        </p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-red-50 flex flex-col items-center justify-center p-8">
        <div className="bg-red-100 border border-red-300 rounded-lg p-6 max-w-lg w-full">
          <h2 className="text-xl font-bold text-red-900 mb-2">
            Errore nel caricamento
          </h2>
          <p className="text-red-800 mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Riprova
          </button>
          <button
            onClick={() => router.push("/")}
            className="mt-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded"
          >
            Torna alla lista
          </button>
        </div>
      </div>
    )
  }

  if (!farmaco) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-8">
        <h2 className="text-xl font-semibold text-gray-900">
          Farmaco non trovato
        </h2>
        <button
          onClick={() => router.push("/")}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Torna alla home
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{farmaco.nome}</h1>
            <p className="text-sm text-gray-600">
              Principio attivo: {farmaco.principio_attivo}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => router.push("/")}
              className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Torna alla lista
            </button>
            <ChatButton
              isOpen={chatOpen}
              onToggle={() => setChatOpen((aperta) => !aperta)}
            />
            <button
              onClick={() => router.push(`/farmaco/${farmacoId}/guida`)}
              className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Guidami
            </button>
            <button
              onClick={() => setScenarioOpen(true)}
              className="px-4 py-2 text-sm font-medium bg-amber-500 text-white rounded hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-400"
            >
              Cosa faccio se…?
            </button>
            <button
              onClick={() => router.push(`/scheda/${farmacoId}`)}
              className="px-4 py-2 text-sm font-medium border border-gray-300 text-gray-700 rounded hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400"
            >
              Condividi
            </button>
            <button
              onClick={() => semplifica()}
              disabled={semplificando}
              className="px-4 py-2 text-sm font-medium bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-green-500"
            >
              {semplificando ? "Semplifico..." : "Semplifica testo"}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-4 py-8">
        <div
          className={`grid grid-cols-1 gap-6 ${
            chatOpen
              ? "lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(340px,0.9fr)]"
              : "lg:grid-cols-2"
          }`}
        >
          <div className="space-y-4">
            <OriginalDocument
              documento={documento}
              fonte={fonteEvidenziata}
              focusNonce={focusFonte}
            />
          </div>

          <div className="space-y-4">
            {semplificando && (
              <div className="bg-white border border-green-200 rounded-lg p-8 flex flex-col items-center justify-center min-h-[200px]">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-green-600 mb-4" />
                <p className="text-sm font-medium text-gray-700">
                  Sto generando la versione semplificata...
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Può richiedere fino a 30 secondi
                </p>
              </div>
            )}

            {!semplificando && simplifyError && (
              <div
                role="alert"
                className="p-4 bg-red-50 rounded border border-red-200 text-sm text-red-800"
              >
                {simplifyError}
              </div>
            )}

            {!semplificando && versioneFacile ? (
              <>
                <EasyText
                  unaFrase={versioneFacile.una_frase}
                  versioneFacile={versioneFacile.versione_facile}
                  glossario={versioneFacile.glossario}
                  domandeFarmacista={versioneFacile.domande_farmacista}
                />
                <div className="mt-3 p-3 bg-blue-50 border border-blue-100 rounded-lg">
                  <p className="text-xs text-blue-900">
                    Qui trovi solo l&apos;essenziale. Per un dettaglio o un
                    dubbio specifico, approfondisci con la chat.
                  </p>
                  <button
                    onClick={() => setChatOpen(true)}
                    disabled={chatOpen}
                    className="mt-2 px-3 py-2 text-xs font-medium bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {chatOpen ? "Chat aperta" : "Approfondisci con la chat"}
                  </button>
                </div>
                <div className="pt-4 border-t border-gray-100 space-y-2">
                  {versioneFacile.cached && (
                    <p className="text-xs text-gray-500 text-center">
                      Versione già disponibile, caricata dalla cache.
                    </p>
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={() => speak(testoDaLeggere)}
                      disabled={ttsLoading}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-green-50 border border-green-200 rounded-lg text-green-700 font-medium hover:bg-green-100 transition-colors disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-green-500"
                    >
                      {ttsLoading
                        ? "Preparo l'audio..."
                        : speaking
                          ? "Riascolta"
                          : "Ascolta versione facile"}
                    </button>
                    {speaking && (
                      <button
                        onClick={stop}
                        className="px-4 py-3 bg-white border border-gray-200 rounded-lg text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400"
                      >
                        Ferma
                      </button>
                    )}
                    <button
                      onClick={() => semplifica(true)}
                      disabled={semplificando || ttsLoading}
                      title="Rigenera la versione semplificata ignorando la cache"
                      className="px-4 py-3 bg-white border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-gray-400"
                    >
                      Rigenera
                    </button>
                  </div>
                  {ttsError && (
                    <p
                      role="alert"
                      className="text-xs text-red-700 text-center"
                    >
                      {ttsError}
                    </p>
                  )}
                </div>
              </>
            ) : !semplificando ? (
              <div className="p-4 bg-amber-50 rounded border border-amber-100 text-center">
                <p className="text-sm text-amber-800">
                  La versione semplificata non è ancora stata generata. Clicca su{" "}
                  <strong>Semplifica testo</strong> per crearla.
                </p>
              </div>
            ) : null}
          </div>

          <div className={chatOpen ? "" : "hidden"}>
            <ChatPanel
              farmacoId={farmacoId}
              isOpen={chatOpen}
              onClose={() => setChatOpen(false)}
              onHighlightSource={evidenziaFonte}
            />
          </div>
        </div>
      </main>

      <ScenarioWizard
        farmacoId={farmacoId}
        open={scenarioOpen}
        onClose={() => setScenarioOpen(false)}
        onHighlightSource={evidenziaFonte}
      />
    </div>
  )
}
