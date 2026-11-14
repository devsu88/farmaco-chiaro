"use client"

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react"
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
import { ChatPanel } from "@/components/ChatPanel"
import { ScenarioWizard } from "@/components/ScenarioWizard"
import { PiuMenu } from "@/components/PiuMenu"
import {
  IconaArrowLeft,
  IconaBookOpen,
  IconaCheckCircle,
  IconaCompass,
  IconaMessage,
  IconaRefresh,
  IconaVolume2,
} from "@/components/Icone"
import { useTTS } from "@/hooks/useTTS"
import {
  registraVersioneGenerata,
  versioneGiaGenerata,
} from "@/lib/versioni-generate"

type Vista = "semplice" | "originale"

const stileTabBase =
  "px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-gray-400"

const stileAzione =
  "inline-flex items-center gap-1.5 border-b pb-0.5 text-[10px] font-semibold uppercase tracking-wider transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-offset-2"
const azioneVerde = `${stileAzione} border-green-700 text-green-700 hover:border-green-800 hover:text-green-800 focus:ring-green-600`
const azioneBlu = `${stileAzione} border-blue-700 text-blue-700 hover:border-blue-800 hover:text-blue-800 focus:ring-blue-500`
const azioneNeutra = `${stileAzione} border-gray-400 text-slate-600 hover:border-slate-600 hover:text-slate-900 focus:ring-gray-400`

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
  const [vista, setVista] = useState<Vista>("semplice")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [simplifyError, setSimplifyError] = useState<string | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [scenarioOpen, setScenarioOpen] = useState(false)
  const [fonteEvidenziata, setFonteEvidenziata] = useState<FonteCitata | null>(
    null
  )
  const [focusFonte, setFocusFonte] = useState(0)

  // Il guard vive in un ref: la callback resta stabile e può essere richiamata
  // dall'effetto di caricamento senza ri-eseguire l'effetto stesso.
  const semplificandoRef = useRef(false)

  const evidenziaFonte = useCallback((fonte: FonteCitata) => {
    setFonteEvidenziata(fonte)
    setFocusFonte((valore) => valore + 1)
    // Una citazione vive nel foglio originale: commutiamo la vista per mostrarla.
    setVista("originale")
  }, [])

  const semplifica = useCallback(
    async (forza = false, mantieniFonte = false) => {
      if (semplificandoRef.current) return
      semplificandoRef.current = true
      setSemplificando(true)
      setSimplifyError(null)

      try {
        const versione = await api.simplify({
          farmaco_id: farmacoId,
          sezione: "tutta",
          forza,
        })
        setVersioneFacile(versione)
        // Con il caricamento automatico la fonte citata dall'URL (o dalla chat)
        // resta l'elemento su cui l'utente è arrivato: non la cancelliamo.
        if (!mantieniFonte) setFonteEvidenziata(null)
        registraVersioneGenerata(farmacoId)
      } catch (err) {
        setSimplifyError(
          err instanceof Error ? err.message : "Semplificazione non disponibile"
        )
      } finally {
        semplificandoRef.current = false
        setSemplificando(false)
      }
    },
    [farmacoId]
  )

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

      // Se il documento citabile non è disponibile, mostriamo le sezioni del
      // dettaglio come fallback: l'utente vede comunque il testo originale.
      if (!documentoCaricato) {
        documentoCaricato = {
          farmaco_id: farmacoCaricato.id,
          documento: `Farmaco ${farmacoCaricato.nome}`,
          sezioni: Object.entries(farmacoCaricato.sezioni).map(
            ([titolo, testo]) => ({
              titolo,
              blocchi: [
                {
                  blocco_id: `sezione-${titolo}`,
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
          setVista("originale")
          break
        }
      }

      // Solo se l'utente ha già generato la versione facile per questo farmaco
      // la ricarichiamo da sola (di norma è in cache sul backend). Con lo
      // storage non disponibile o il farmaco mai generato resta il CTA.
      if (versioneGiaGenerata(farmacoId)) {
        void semplifica(false, true)
      }
    }

    carica()
    return () => {
      cancelled = true
    }
  }, [farmacoId, semplifica])

  const testoDaLeggere = versioneFacile
    ? [versioneFacile.una_frase, ...versioneFacile.versione_facile].join(" ")
    : ""

  const onKeyDownTab = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return
    event.preventDefault()
    const nuova: Vista = vista === "semplice" ? "originale" : "semplice"
    setVista(nuova)
    document.getElementById(`tab-${nuova}`)?.focus()
  }

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
    <div className="min-h-screen bg-[#fbfcfe]">
      <header className="sticky top-0 z-20 border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-3xl px-4 py-3">
          <div className="flex items-start gap-2">
            <button
              type="button"
              onClick={() => router.push("/")}
              aria-label="Torna alla home"
              className="-ml-1.5 mt-0.5 rounded p-1.5 text-slate-600 transition-colors hover:bg-gray-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <IconaArrowLeft size={18} />
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold text-slate-900">
                {farmaco.nome}
              </h1>
              <p className="truncate text-xs text-slate-500">
                {farmaco.principio_attivo} · Foglio illustrativo AIFA
              </p>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-3">
            <div
              role="tablist"
              aria-label="Vista del foglio illustrativo"
              onKeyDown={onKeyDownTab}
              className="inline-flex border border-gray-200 p-0.5"
            >
              <button
                id="tab-semplice"
                type="button"
                role="tab"
                aria-selected={vista === "semplice"}
                aria-controls="pannello-semplice"
                onClick={() => setVista("semplice")}
                className={`${stileTabBase} ${
                  vista === "semplice"
                    ? "bg-gray-900 text-white"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Semplice
              </button>
              <button
                id="tab-originale"
                type="button"
                role="tab"
                aria-selected={vista === "originale"}
                aria-controls="pannello-originale"
                onClick={() => setVista("originale")}
                className={`${stileTabBase} ${
                  vista === "originale"
                    ? "bg-gray-900 text-white"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Originale
              </button>
            </div>

            {versioneFacile && (
              <button
                type="button"
                onClick={() => speak(testoDaLeggere)}
                disabled={ttsLoading}
                aria-label={
                  ttsLoading
                    ? "Preparo l'audio"
                    : speaking
                      ? "Riascolta la versione facile"
                      : "Ascolta la versione facile"
                }
                className={azioneVerde}
              >
                <IconaVolume2 size={13} />
                {ttsLoading
                  ? "Preparo l'audio..."
                  : speaking
                    ? "Riascolta"
                    : "Ascolta"}
              </button>
            )}

            <button
              type="button"
              onClick={() => router.push(`/farmaco/${farmacoId}/guida`)}
              className="inline-flex items-center gap-1.5 bg-blue-600 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <IconaCompass size={13} />
              Guidami
            </button>

            <div className="ml-auto">
              <PiuMenu
                chatAperta={chatOpen}
                onApriChat={() => setChatOpen(true)}
                onApriScenario={() => setScenarioOpen(true)}
                onCondividi={() => router.push(`/scheda/${farmacoId}`)}
                onRigenera={() => semplifica(true)}
              />
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-6">
        {!semplificando && simplifyError && (
          <div
            role="alert"
            className="mb-4 p-4 bg-red-50 rounded border border-red-200 text-sm text-red-800"
          >
            {simplifyError}
          </div>
        )}

        {vista === "originale" ? (
          <div
            role="tabpanel"
            id="pannello-originale"
            aria-labelledby="tab-originale"
          >
            <OriginalDocument
              documento={documento}
              fonte={fonteEvidenziata}
              focusNonce={focusFonte}
            />
          </div>
        ) : (
          <div
            role="tabpanel"
            id="pannello-semplice"
            aria-labelledby="tab-semplice"
            className="space-y-4"
          >
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

            {!semplificando && versioneFacile && (
              <>
                <EasyText
                  unaFrase={versioneFacile.una_frase}
                  versioneFacile={versioneFacile.versione_facile}
                  glossario={versioneFacile.glossario}
                  domandeFarmacista={versioneFacile.domande_farmacista}
                />

                <div className="border border-gray-200 border-l-[3px] border-l-blue-600 bg-white p-4">
                  <p className="text-sm text-slate-600">
                    Qui trovi solo l&apos;essenziale. Per un dettaglio o un
                    dubbio specifico, approfondisci con la chat.
                  </p>
                  <button
                    type="button"
                    onClick={() => setChatOpen(true)}
                    disabled={chatOpen}
                    className={`${azioneBlu} mt-3`}
                  >
                    <IconaMessage size={13} />
                    {chatOpen ? "Chat aperta" : "Chiedi alla chat"}
                  </button>
                </div>

                <div className="border-t border-gray-200 pt-4">
                  {versioneFacile.cached && (
                    <p className="text-xs text-slate-500">
                      Versione già disponibile, caricata dalla cache.
                    </p>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-3">
                    <button
                      type="button"
                      onClick={() => speak(testoDaLeggere)}
                      disabled={ttsLoading}
                      className={azioneVerde}
                    >
                      <IconaVolume2 size={13} />
                      {ttsLoading
                        ? "Preparo l'audio..."
                        : speaking
                          ? "Riascolta"
                          : "Ascolta la versione facile"}
                    </button>
                    {speaking && (
                      <button
                        type="button"
                        onClick={stop}
                        className={azioneNeutra}
                      >
                        Ferma
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => semplifica(true)}
                      disabled={semplificando || ttsLoading}
                      title="Rigenera la versione semplificata ignorando la cache"
                      className={azioneNeutra}
                    >
                      <IconaRefresh size={13} />
                      Rigenera
                    </button>
                  </div>
                  {ttsError && (
                    <p role="alert" className="mt-2 text-xs text-red-700">
                      {ttsError}
                    </p>
                  )}
                </div>
              </>
            )}

            {!semplificando && !versioneFacile && (
              <>
                <section className="border border-gray-200 border-l-[3px] border-l-green-600 bg-gray-50 p-5">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-green-700">
                    Versione facile da leggere
                  </p>
                  <h2 className="mt-2 text-base font-semibold text-slate-900">
                    Faccio una versione semplice e chiara del foglio
                    illustrativo.
                  </h2>
                  <p className="mt-1 text-sm text-slate-600">
                    Parte dal testo AIFA e non cambia dosi né avvertenze.
                  </p>
                  <button
                    type="button"
                    onClick={() => semplifica()}
                    disabled={semplificando}
                    className="mt-4 inline-flex items-center gap-2 bg-green-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-green-800 disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-green-600 focus:ring-offset-2"
                  >
                    <IconaCheckCircle size={15} />
                    Genera la versione facile
                  </button>
                </section>

                <details className="border border-gray-200 bg-white">
                  <summary className="cursor-pointer list-none px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-600 transition-colors hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500">
                    <span className="inline-flex items-center gap-2">
                      <IconaBookOpen size={13} />
                      Vedi anche il foglio originale
                    </span>
                  </summary>
                  <div className="border-t border-gray-200 p-3">
                    <OriginalDocument
                      documento={documento}
                      fonte={fonteEvidenziata}
                      focusNonce={focusFonte}
                    />
                  </div>
                </details>
              </>
            )}
          </div>
        )}

        <p className="mt-8 text-[10px] text-slate-400">
          Fonte: fogli illustrativi AIFA · Non sostituisce il parere del medico
          o del farmacista.
        </p>
      </main>

      {chatOpen && (
        <>
          <div
            aria-hidden="true"
            onClick={() => setChatOpen(false)}
            className="fixed inset-0 z-20 bg-black/30"
          />
          <div className="fixed inset-y-0 right-0 z-30 flex w-full flex-col overflow-hidden border-l border-gray-200 bg-white shadow-xl sm:max-w-md [&>section]:h-full [&>section]:rounded-none [&>section]:border-0 [&>section]:shadow-none">
            <ChatPanel
              farmacoId={farmacoId}
              isOpen={chatOpen}
              onClose={() => setChatOpen(false)}
              onHighlightSource={evidenziaFonte}
            />
          </div>
        </>
      )}

      <ScenarioWizard
        farmacoId={farmacoId}
        open={scenarioOpen}
        onClose={() => setScenarioOpen(false)}
        onHighlightSource={evidenziaFonte}
      />
    </div>
  )
}
