# Intent: osservabilità e verifica del deploy

Autore: maintainer del progetto. Data: 2026-11-20. Stato: **draft**, da
correggere e approvare prima della spec.

## Problema

L’hardening ha aggiunto log JSON e limiti, ma non sappiamo se il codice che
gira in produzione è quello che abbiamo mergiato. Lo smoke test del 2026-11-20
ha mostrato:

- `/` risponde `200`, `/api/rag/status` riporta 621 farmaci e Qdrant
  disponibile, `/api/farmaco/012745_01` e la pagina del farmaco rispondono
  `200`;
- l’ultimo deploy Production su Vercel ha **2 giorni**, mentre `main` ha i
  commit di oggi;
- la produzione **non** restituisce `X-Request-ID` e accetta
  `POST /api/chat` con `messaggio: ""`, quindi non contiene l’hardening;
- un push su `main` non ha creato un nuovo deploy Production.

Inoltre i log strutturati esistono solo come righe su stdout: non c’è un
report di latenza, `429`, `502/504` o costo per modello, e non c’è un alert di
budget. Non c’è uno smoke test post-deploy che dica “questa release funziona”.

Il rischio è duplice: credere di aver spedito una protezione che non è live, e
non accorgersi di un picco di costo o di errori finché non lo dice un utente.

## Esito proposto

1. **Identità della release.** `/health` (o `/version`) espone il commit SHA e
   il timestamp di build, letti da `VERCEL_GIT_COMMIT_SHA` o iniettati nel
   build. Un `curl` dice subito quale codice sta rispondendo.
2. **Smoke test post-deploy.** Uno script (`make smoke` o
   `scripts/smoke.py`) verifica in produzione, senza chiamare l’LLM:
   home, `/api/rag/status`, una pagina farmaco, `422` su chat con messaggio
   vuoto, presenza di `X-Request-ID`. Esce non-zero se qualcosa manca.
3. **Report periodico.** Un job settimanale o un comando locale aggrega i log:
   p50/p95 di latenza per chat/simplify/tts, percentuale di `429` e
   `502/504`, chiamate per modello, costo stimato. Soglia di budget con
   alert.
4. **Deploy esplicito e verificato.** Il deploy Production resta manuale e
   autorizzato; dopo il deploy si esegue lo smoke test e si confronta lo SHA
   con `main`.

Riconoscimento del successo: dopo un merge, in meno di un minuto si sa se la
produzione serve quel commit; dopo una settimana si sa quanto è costata, quanto
è stata lenta e quanti `429` ha prodotto.

## Utenti e sistemi toccati

- Maintainer e on-call.
- Backend FastAPI (`/health` o `/version`), CI GitHub Actions, Vercel.
- Nessun cambiamento al contenuto o al comportamento clinico.

## Vincoli

- I log JSON esistono già; non si aggiunge un servizio se il log drain di
  Vercel o un job che legge l’API bastano.
- Nessun dato personale: resta l’hash dell’IP, mai il contenuto dei messaggi.
- Lo smoke test non deve chiamare l’LLM né consumare budget.
- Il deploy Production non viene automatizzato in questa iterazione: si
  aggiungono identità e verifica.
- Le nuove variabili d’ambiente hanno default sicuri.

## Non-obiettivi

- OTel completo o una dashboard esterna se il log drain basta.
- Autenticazione, captcha, account utente.
- Alerting 24/7 e un servizio di on-call.
- Automazione del rollback o del deploy da un agente.

## Domande aperte

1. **Dove aggregare i log?** Vercel log drain verso un servizio (Better Stack,
   Datadog) oppure un job GitHub che interroga l’API Vercel? La scelta cambia
   costo e dipendenze.
2. **Budget:** qual è la soglia mensile accettabile e chi riceve l’alert?
3. **Commit SHA:** `VERCEL_GIT_COMMIT_SHA` è disponibile nel container? Se non
   lo è, va iniettato nel build come variabile o scritto in un file.
4. **Smoke test:** deve girare su ogni push a `main`, solo dopo un deploy
   manuale, o entrambi?
5. **Deploy:** resta manuale (`vercel --prod`) o si passa a Git integration con
   un gate di approvazione? Oggi il push su `main` non deploya.
6. **Costo:** si stima dai token restituiti dal provider o da un prezzo per
   chiamata configurato? Il modello è su OpenRouter e il free tier può cambiare.

## Baseline misurata (2026-11-20)

- `GET /` → `200`.
- `GET /api/rag/status` → `621` farmaci, Qdrant `available: true`, 12.947
  vettori.
- `GET /api/farmaco/012745_01` → `200`; `GET /api/farmaco/012745_01/documento`
  → `200`; `GET /farmaco/012745_01` → `200`.
- `GET /api/farmaci/012745_01` → `404`: il path pubblico è singolare, il
  plurale è interno al backend.
- `POST /api/chat` con `messaggio: ""` → `200` con risposta reale: produzione
  pre-hardening.
- Ultimo deploy Production Vercel: 2 giorni; nessun deploy creato dal push su
  `main`.

## Prossimo passo

Rispondere alle domande 1–5, poi scrivere `spec.md` e `plan.md`. La prima
correzione, indipendente dalle risposte, è rendere verificabile la release
(commit SHA + smoke test).
