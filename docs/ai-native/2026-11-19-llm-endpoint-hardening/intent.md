# Intent: contenere costo e abuso degli endpoint LLM

Autore: maintainer del progetto. Data: 2026-11-19. Stato: **accettato il
2026-11-20** con i default indicati nella sezione “Decisioni”.

## Problema

La demo è pubblica e gli endpoint che chiamano il provider non hanno limiti.
Oggi:

- `ChatRequest` accetta un `messaggio` senza lunghezza massima e uno `storico`
  senza numero massimo di turni (`backend/app/schemas.py`).
- `SimplifyRequest` accetta `testo` arbitrario: chiunque può inviare un testo
  lungo e far pagare al progetto una semplificazione completa.
- Non esiste rate limiting per IP o sessione su `/api/chat`, `/api/simplify` e
  `/api/tts`.
- Il proxy Next (`frontend/src/lib/backend.ts`) non impone un timeout: una
  richiesta lenta tiene occupata una funzione fino al timeout della piattaforma.
- Non ci sono log strutturati, metriche di latenza o costo per provider, quindi
  non si può sapere se qualcuno sta abusando del servizio né quanto costa.

Il rischio non è un bug funzionale: è che un singolo client, un crawler o un
test di carico consumino la quota e il budget, rendendo la demo inutilizzabile
per tutti. È anche un rischio di prompt injection: il testo libero di
`/api/simplify` finisce nel prompt senza essere un blocco del foglietto.

## Esito proposto

1. Ogni input LLM ha un limite esplicito e un messaggio d'errore comprensibile:
   `messaggio`, numero di turni dello storico, lunghezza del testo da
   semplificare.
2. Gli endpoint costosi hanno un rate limit con risposta `429` e
   `Retry-After`; il limite è abbastanza alto da non disturbare un utente reale.
3. Il proxy e il backend hanno un timeout coerente con la latenza osservata
   (chat 6–10 s, semplificazione 10–27 s) e restituiscono `504` invece di
   restare appesi.
4. Ogni richiesta LLM produce un log strutturato con endpoint, durata, esito,
   modello e (quando disponibile) token/costo stimato.
5. I test coprono i limiti, il `429`, il `504` e il fatto che un input normale
   non venga rifiutato.

Riconoscimento del successo: un client che invia 100 richieste al minuto riceve
`429`; un testo di 1 MB riceve `413`/`422`; una richiesta al provider bloccata
fallisce entro il budget di tempo; i log permettono di ricostruire chi ha
consumato cosa.

## Utenti e sistemi toccati

- Visitatori della demo: devono continuare a usare chat e semplificazione
  senza attriti.
- Backend FastAPI: schemi, route, middleware, client LLM.
- Proxy Next.js: timeout e propagazione degli errori.
- CI: nuovi test deterministici; nessuna chiamata reale al provider.
- Deploy Vercel: comportamento per istanza, se il limite è in memoria.

## Vincoli

- Nessuna nuova dipendenza runtime se una soluzione con middleware FastAPI e
  standard library basta per la demo.
- I test restano offline e deterministici (`RETRIEVAL_MODE=bm25`, nessuna
  chiamata a OpenRouter).
- Non si rompe il contratto pubblico delle risposte oltre l'aggiunta di codici
  di errore e header.
- I contenuti e i prompt non cambiano: questo intervento non tocca la sicurezza
  medica.
- Il rate limit deve funzionare su più istanze o essere dichiarato come
  best-effort per istanza. Vercel container non garantisce stato condiviso.

## Non-obiettivi

- Autenticazione, account utente, captcha o verifica umana.
- Redis/Upstash o un servizio di rate limiting gestito: da valutare solo se il
  limite in memoria non è sufficiente per il rischio accettato.
- Streaming delle risposte, sessione persistente, cache condivisa.
- Rifacimento del grafo LangGraph o dei prompt.
- Dashboard di osservabilità: qui bastano log strutturati e una metrica minima.

## Domande aperte

1. **Modello di rischio**: la demo è pubblica e senza autenticazione. Un limite
   in memoria per istanza è accettabile, o serve subito uno store condiviso?
   La risposta cambia se il deploy è a una o più istanze e se il budget è
   tollerabile.
2. **Soglie**: propongo 20 richieste/minuto per IP su chat e simplify, 10/minuto
   su TTS, `messaggio` ≤ 1.000 caratteri, storico ≤ 10 turni, `testo` ≤ 12.000
   caratteri (lo stesso limite già usato da `ETR_MAX_CARATTERI_FONTE`). Vanno
   confermate o corrette.
3. **Timeout**: il client LLM ha 90 s. Il proxy dovrebbe stare sopra (es. 100 s)
   o sotto? Un timeout del proxy più basso taglia le semplificazioni lente ma
   libera prima la funzione.
4. **Osservabilità**: basta un log JSON su stdout (Vercel li raccoglie) o serve
   OTel verso un backend? La scelta cambia dipendenze e costo.
5. **Chi possiede il budget** e chi riceve l'allarme quando il costo giornaliero
   supera una soglia.
6. **Prompt injection**: `/api/simplify` con `testo` libero è un caso d'uso
   reale o si può limitare ai soli blocchi del foglietto? Se è reale, va
   trattato come input non fidato e validato.

## Decisioni (2026-11-20)

1. **Rate limit in memoria per istanza.** È accettato come best-effort per la
   demo; se il traffico cresce o il budget lo richiede, si passa a uno store
   condiviso con una nuova spec.
2. **Soglie confermate:** 20 req/min per IP su chat e simplify, 10 req/min su
   TTS, finestra 60 s; `messaggio` ≤ 1.000 caratteri, storico ≤ 10 turni,
   `testo` ≤ 12.000 caratteri. In più: ogni messaggio dello storico ≤ 2.000
   caratteri e corpo richiesta ≤ 2 MB.
3. **Timeout:** client LLM 90 s, proxy Next 100 s. Il proxy sta sopra il
   provider per non tagliare le semplificazioni lente; si abbasserà dopo aver
   misurato.
4. **Log:** JSON su stdout, raccolti da Vercel. Niente OTel in questa
   iterazione.
5. **Proprietà del budget:** resta al maintainer; la soglia di allarme è
   documentata ma non automatizzata.
6. **`/api/simplify` con testo libero:** resta supportato per ora, ma è
   trattato come input non fidato: limite di 12.000 caratteri e nessuna
   aspettativa di fedeltà al foglietto quando il testo non proviene dai blocchi.

## Prossimo passo

Scrivere `spec.md` e `plan.md`, poi implementare con TDD.
