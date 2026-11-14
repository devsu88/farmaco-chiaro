# Revisione UX Frontend — Piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ristrutturare home e pagina farmaco del frontend per dare gerarchia, accoglienza e micro-feedback, secondo il design approvato.

**Architecture:** Solo frontend Next.js App Router + Tailwind (`frontend/src/`), zero modifiche backend e zero nuove dipendenze. Le nuove feature si appoggiano a 3 piccoli moduli in `src/lib/` (lista curata, ricerche recenti, registro versioni generate) e a 2 componenti nuovi (`PiuMenu`, `Skeleton`, `Toast`); le pagine esistenti vengono ristrutturate senza toccare la logica API.

**Tech Stack:** Next.js 16.4.5 (App Router, Client Components), React 19, Tailwind CSS 3.4, TypeScript 5. Consultare `frontend/node_modules/next/dist/docs/` prima di scrivere routing/client code.

**Spec:** `docs/superpowers/specs/2026-11-14-ux-revisione-frontend-design.md` (+ mockup autentici in `docs/superpowers/specs/2026-11-14-ux-mockups/*.html`)

## Global Constraints

- Nessuna modifica a `backend/`; nessuna nuova dipendenza npm (restano quelle in `frontend/package.json`).
- Palette: **verde** = versione facile/lettura (`green-*` Tailwind), **blu** = approfondire/chat/Guidami (`blue-*`), **ambra** = scenari/fonti/avvisi (`amber-*`/`yellow-*`). Coerente con l'uso già presente in `EasyText.tsx` e `ScenarioWizard.tsx`.
- Accessibilità non negoziabile: preservare o migliorare tutti i `role`, `aria-*`, `focus:ring-2`, e il focus management esistenti. Niente contrasto sotto WCAG AA.
- `localStorage` sempre dentro `try/catch` (Safari private mode lo blocca): un fallimento di storage non deve mai rompere il rendering.
- Testo sempre in italiano, registro informale-ma-rispettoso già usato nell'app («Sto caricando…», «Può richiedere fino a 30 secondi»).
- Il frontend non ha test runner: il ciclo di verifica di ogni task è `npm run lint` (ESLint, da `frontend/`) + `npm run build` (fa anche il type-check TS) + verifica manuale nel browser elencata nel task.
- Prima di scrivere codice Client Component o routing, consultare `frontend/node_modules/next/dist/docs/` (API Next 16 cambiate rispetto ai ricordi).
- **Stile visivo "editoriale clinico" (ruling utente 2026-11-14, dettagli nella sezione omonoma della spec):** superfici bianche con bordi sottili `gray-200`, accenti a barra verticale laterale, azioni come link-azioni maiuscoletti sottolineati con icona, label tecniche in maiuscolo con `tracking-wider`, un solo bottone pieno per schermata al massimo (nero `bg-gray-900`), disclaimer AIFA nelle pagine di contenuto, emoji eliminate dall'interfaccia.
- **Icone:** componenti SVG inline (path Lucide, tratteggio 2px, `aria-hidden`) nel modulo `frontend/src/components/Icone.tsx` creato dal Task 2R — nessuna dipendenza npm. I task 3-9 consumano questo modulo e non introducono emoji nuove.

## Review Focus

Gli input che la spec implica ma che i passi "felici" dei task non esercitano, con il test che li fissa:

1. **Ricerca con errore di rete** (backend giù): l'utente vede il messaggio di errore nel dropdown, non un silenzio che sembra "nessun risultato". → Task 3, passo di verifica manuale con backend fermo.
2. **`localStorage` non disponibile** (Safari privato, storage disabilitato): home e pagina farmaco rendono normalmente, solo senza ricerche recenti/auto-caricamento. → Task 1 (helpers in try/catch, testato con mock che lancia) e Task 5 ( verifica: aprire pagina con storage bloccato da DevTools).
3. **Deep link `?fonte=<blocco_id>`** (da modalità guidata): la vista deve partire su "Originale" col blocco in evidenza, non sul default "Semplice". → Task 5, passo di verifica manuale.
4. **Fonte citata dalla chat mentre la vista è su "Semplice"**: la vista commuta da sola su "Originale" col flash sul blocco, senza che l'utente cerchi a mano. → Task 5 e 6, passo di verifica manuale.
5. **Farmaco mai generato su dispositivo nuovo** (registro locale vuoto ma cache backend calda): appare il CTA «Genera la versione facile», mai una generazione automatica. → Task 5, passo di verifica manuale con storage pulito.

---

### Task 1: Moduli lib — lista curata, ricerche recenti, registro versioni

**Files:**
- Create: `frontend/src/lib/farmaci-comuni.ts`
- Create: `frontend/src/lib/ricerche-recenti.ts`
- Create: `frontend/src/lib/versioni-generate.ts`

**Interfaces:**
- Consumes: nulla (moduli puri, nessuna API).
- Produces (usati dai Task 2 e 5):
  - `farmaci-comuni.ts`: `export interface FarmacoComune { id: string; nome: string }` e `export const FARMACI_COMUNI: FarmacoComune[]` (5 voci).
  - `ricerche-recenti.ts`: `export function leggiRicercheRecenti(): string[]` (max 3, più recenti prima), `export function aggiungiRicercaRecente(nome: string): void` (dedup, max 3), `export function cancellaRicercheRecenti(): void`. Chiave storage: `"fc-ricerche-recenti"`.
  - `versioni-generate.ts`: `export function versioneGiaGenerata(farmacoId: string): boolean`, `export function registraVersioneGenerata(farmacoId: string): void`. Chiave storage: `"fc-versioni-generate"` (JSON array di id).

- [ ] **Step 1: Curare la lista `FARMACI_COMUNI` dal dataset reale**

  Cercare nel dataset i fogli di farmaci molto comuni (antipiretici, gastro-protezione, antinfiammatori). Comando:

  ```bash
  grep -i -o '"foglio": "[^"]*NOME[0-9 ]*[^"]*"' backend/data/rag/sections.jsonl | sort -u | head -5
  ```

  Candidati confermati dal dataset: Tachipirina (comprime 1000 mg), Gaviscon Advance, Moment 200 mg. Completare a 5 con altri brand presenti nel dataset verificati con lo stesso comando (es. cercare XAMAMINA, ENTEROGERMINA, FRAGIL). Registrare per ogni voce l'esatto `farmaco_id` (`"002955_01"` formato) e il nome leggibile (`"Tachipirina"` senza formato/dosaggio). Se un candidato non esiste nel dataset, sostituirlo con un altro trovato dal grep — mai inventare id.

- [ ] **Step 2: Implementare i tre moduli**

  Ogni funzione che tocca `localStorage` va interamente in `try/catch` e ritorna valore di default vuoto/`false` su errore. Nessun altro effetto collaterale.

- [ ] **Step 3: Verifica lint + build**

  Run: `cd frontend && npm run lint && npm run build`
  Expected: entrambi senza errori. La degradazione con storage bloccato si verifica nei Task 2 e 5, dove i moduli vengono usati nel rendering.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/lib/farmaci-comuni.ts frontend/src/lib/ricerche-recenti.ts frontend/src/lib/versioni-generate.ts
  git commit -m "feat(ui): moduli lib per farmaci comuni, ricerche recenti e registro versioni"
  ```

### Task 2: Home — porta d'ingresso

**Files:**
- Modify: `frontend/src/app/page.tsx` (intero file, ~47 righe oggi)
- Consumes: `FARMACI_COMUNI` (Task 1), `leggiRicercheRecenti`/`aggiungiRicercaRecente`/`cancellaRicercheRecenti` (Task 1). Icone: emoji dirette (📖 ✅ 🔊 💊) come nei mockup approvati — `lib/icone.ts` non ha questi simboli e il mapping esiste solo per la modalità guidata.

**Interfaces:**
- Consumes: firma `SearchBar` invariata (`onSelect: (farmacoId: string) => void`), Task 3 cambierà solo il comportamento interno del dropdown.
- Produces: pagina home con: hero gradiente `from-blue-100 to-sky-100`, chip farmaci comuni (click → `router.push('/farmaco/<id>')`), riga ricerche recenti con bottone "cancella", 3 card feature. I testi esatti sono nei mockup `proposte-overview.html` e `dettaglio-p1-p2.html` (validati dall'utente): riprodurli fedelmente.

- [ ] **Step 1: Ristrutturare `page.tsx`**

  Layout per il mockup `dettaglio-p1-p2.html` (colonna sinistra): hero centrato con `💊`, titolo `text-2xl font-bold text-sky-900`, claim «Il foglio illustrativo, spiegato in modo facile da leggere», `SearchBar` (max-w-md centrata). Sotto: etichetta «Più cercati questa settimana:» + chip (pill bianche bordo `blue-300`, testo `blue-700`, hover `bg-blue-50`). Riga ricerche recenti caricata con `useEffect` via `leggiRicercheRecenti()` solo lato client (la pagina è già `"use client"`); ogni recent è un bottone che fa `router.push` e chiama `aggiungiRicercaRecente`; bottone ✕ «Cancella» con `cancellaRicercheRecenti()`). Nota privacy: «solo sul tuo dispositivo». In basso: 3 card (`📖 Trova il farmaco` / `✅ Leggi la versione facile` / `🔊 Ascolta o chiedi`) affiancate su `sm+`, impilate su mobile, con sottotitoli dal mockup.

- [ ] **Step 2: Verifica lint + build**

  Run: `cd frontend && npm run lint && npm run build`
  Expected: nessun errore; nessun errore di idratazione in build (le ricerche recenti si leggono in `useEffect`, mai nel render iniziale).

- [ ] **Step 3: Verifica manuale nel browser**

  `make frontend` (o `npm run dev`): hero visibile, chip navigano alla pagina giusta (id del Task 1), ricerche recenti appaiono dopo il primo navigato e sopravvivono al reload, bottone cancella le svuota, con storage bloccato la pagina rende senza recenti e senza errori in console.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/app/page.tsx
  git commit -m "feat(ui): home come porta d'ingresso con farmaci comuni e ricerche recenti"
  ```

### Task 2R: Allineamento home allo stile C + modulo icone (ruling utente)

**Files:**
- Create: `frontend/src/components/Icone.tsx`
- Modify: `frontend/src/app/page.tsx`
- Consumes: tutto l'esistente del Task 2 (moduli lib, layout, logica) — cambia SOLO il rivestimento visivo.
- Produce (consumato dai task 3-9): modulo `Icone.tsx` con componenti SVG inline Lucide (tratteggio 2px, `aria-hidden="true"`):
  ```ts
  // firma unica per tutte le icone; ogni icona è un named export
  export function IconaSearch({ size = 16, className = "" }: { size?: number; className?: string })
  // nomi richiesti: IconaSearch, IconaInfo, IconaVolume2, IconaHeadphones,
  // IconaCompass, IconaMessage, IconaShare, IconaMore, IconaX,
  // IconaArrowLeft, IconaArrowRight, IconaBookOpen, IconaCheckCircle,
  // IconaClock, IconaTestoGrande, IconaContrasto, IconaRefresh
  ```
  (path SVG Lucide; se un nome non serve in un task successivo si omette, ma le icone usate devono venire da questo modulo, mai emoji nuove)

- [ ] **Step 1: Creare `Icone.tsx` con le icone richieste dal mockup validato**
  Mockup di riferimento: `docs/superpowers/specs/2026-11-14-ux-mockups/schermate-stile-c-iconset.html` — gli SVG sono già lì, si copiano i path. Colore via `currentColor`, dimensione via prop `size`.

- [ ] **Step 2: Riallineare `page.tsx` allo stile C (stessa logica, nuovo rivestimento)**
  - Header bianco con logo testuale FARMACO**CHIARO** + etichetta «FOGLI ILLUSTRATIVI AIFA» (sostituisce il gradiente e l'emoji 💊).
  - Titolo con barra laterale blu (`border-l-2 border-blue-600 pl-3`), claim invariato.
  - SearchBar invariata (Task 3 la lavora), sfondo pagina grigio chiarissimo.
  - Chips «Più consultati» come link sottolineati blu (`border-b border-blue-600 text-blue-800`), etichetta label tecnica maiuscolo.
  - Riga ricerche recenti con `IconaInfo` e ✕ sostituita da `IconaX`; privacy note invariata.
  - Le 3 card diventano colonne divise da `border-r` con `IconaBookOpen`/`IconaCheckCircle`/`IconaHeadphones` in alto, titoli TROVA/LEGGI/ASCOLTA in maiuscolo tecnico, niente sfondi pieni.
  - Footer disclaimer AIFA.
- [ ] **Step 3: Verifica lint + build** (`cd frontend && npm run lint && npm run build`), nessun errore, nessun mismatch di idratazione.
- [ ] **Step 4: Commit**
  ```bash
  git add frontend/src/components/Icone.tsx frontend/src/app/page.tsx
  git commit -m "feat(ui): home allineata allo stile editoriale clinico con modulo icone SVG"
  ```

### Task 3: SearchBar — empty state e stato di errore

**Files:**
- Modify: `frontend/src/components/SearchBar.tsx` (solo blocco risultati, righe ~29-51 e ~165-190)

**Interfaces:**
- Consumes: invariato.
- Produces: `SearchBar` con stessa firma pubblica; nuovo stato interno `stato: "loading" | "risultati" | "vuoto" | "errore"` che determina l'apertura del dropdown. Il comportamento oggi: `setIsOpen(res.risultati.length > 0)` — il dropdown non si apre a vuoto; da ora si apre anche per `vuoto` ed `errore`.

- [ ] **Step 1: Aggiungere gli stati vuoto ed errore al dropdown**

  In `cerca()`: su risposta con zero risultati → `setIsOpen(true)` e stato `vuoto`; su `catch` → `setIsOpen(true)` e stato `errore` (i `runIdRef` guard esistenti restano: risposte superate non riaprono il dropdown). Render nel dropdown:
  - `vuoto`: «Non ho trovato «<query>». Prova con il principio attivo (es. paracetamolo invece di Tylenol).» — testo `text-sm text-gray-700`, padding `p-4`.
  - `errore`: «La ricerca non è al momento disponibile. Controlla la connessione e riprova.» — testo `text-sm text-red-700`, `role="alert"`.
  Entrambi con `role="status"`/`role="alert"` letti da screen reader quando il dropdown si apre.

- [ ] **Step 2: Verifica lint + build**

  Run: `cd frontend && npm run lint && npm run build`
  Expected: nessun errore.

- [ ] **Step 3: Verifica manuale (Review Focus 1)**

  Con backend fermo (non eseguire `make backend`): digitare «tachipirina» → messaggio rosso di errore visibile e leggibile. Con backend attivo: digitare «tylenol» → messaggio «Non ho trovato…» con suggerimento paracetamolo; digitare «tachipirina» → risultati normali come prima.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/components/SearchBar.tsx
  git commit -m "feat(ui): searchbar con empty state e stato di errore espliciti"
  ```

### Task 4: PiuMenu — menu secondari della pagina farmaco

**Files:**
- Create: `frontend/src/components/PiuMenu.tsx`

**Interfaces:**
- Consumes: nulla.
- Produces (usato dal Task 5):
  ```ts
  interface PiuMenuProps {
    chatAperta: boolean
    onApriChat: () => void
    onApriScenario: () => void
    onCondividi: () => void
    onRigenera: () => void
  }
  export function PiuMenu(props: PiuMenuProps)
  ```
  Bottone "⋯" (aria-label «Altre funzioni», `aria-expanded`) che apre dropdown con: «Chiedi al chatbot» (o «Nascondi chatbot» se `chatAperta`), «Cosa faccio se…?», «Condividi», «Rigenera versione facile». Chiude su click esterno e `Escape` (pattern `pointerdown`/`keydown` su `document` già usato in `SearchBar.tsx:58-77`). Voce attiva di chat disabilitata quando `chatAperta` (come `ClientPage.tsx:318-323` oggi).

- [ ] **Step 1: Implementare il componente**

  Dropdown `absolute right-0 mt-2 w-64 bg-white border rounded-lg shadow-lg z-30`, voci `button` full-width `text-left px-4 py-2.5 text-sm hover:bg-gray-50`.

- [ ] **Step 2: Verifica lint + build**

  Run: `cd frontend && npm run lint && npm run build`
  Expected: nessun errore.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/components/PiuMenu.tsx
  git commit -m "feat(ui): componente PiuMenu per funzioni secondarie"
  ```

### Task 5: Pagina farmaco — header, toggle, drawer, auto-caricamento

Il task più grosso: ristruttura `ClientPage.tsx` mantenendo invariati i componenti figli (`OriginalDocument`, `EasyText`, `ChatPanel`, `ScenarioWizard`, `ChatButton` non serve più come bottone header — viene usato dentro `PiuMenu`? No: `ChatButton` resta importabile ma il nuovo header non lo usa; il pulsante chat vive in `PiuMenu`).

**Files:**
- Modify: `frontend/src/app/farmaco/[id]/ClientPage.tsx`
- Consumes: `versioneGiaGenerata`/`registraVersioneGenerata` (Task 1), `PiuMenu` (Task 4). Invariati: `api.*`, `useTTS`, `OriginalDocument`, `EasyText`, `ChatPanel`, `ScenarioWizard`.

**Interfaces:**
- Consumes: firme esistenti di `api.simplify({farmaco_id, sezione, forza})` → `SimplifyResponse` con campo `cached`; `evidenziaFonte(fonte)` già presente (`ClientPage.tsx:45-48`).
- Produces: nuovo stato `vista: "semplice" | "originale"` (default `"semplice"`); `evidenziaFonte` ora commuta anche `vista` su `"originale"`; il parsing `?fonte=` (righe 105-123) imposta `vista = "originale"` quando trova il blocco. Layout: niente più grid a colonne (`ClientPage.tsx:267-288`); header sticky con toggle segmentato.

- [ ] **Step 1: Nuovo header**

  Struttura (mockup `dettaglio-p1-p2.html`, colonna destra): riga 1 = link «←» (aria-label «Torna alla home», `router.push("/")`) + nome + principio attivo. Riga 2 = toggle segmentato `[Semplice | Originale]` (contenitore `bg-gray-100 rounded-lg p-1`, opzione attiva `bg-white shadow-sm text-gray-900 font-medium`, inattiva `text-gray-600`; `role="tablist"` + `role="tab"` con `aria-selected`), pulsante 🔊 (`aria-label` dinamico «Ascolta versione facile»/preparo/riascotta come oggi `ClientPage.tsx:332-342`), CTA `🧭 Guidami` (blu primario, come `ClientPage.tsx:237-242`), `PiuMenu` a destra. Il pulsante 🔊 appare solo quando esiste `versioneFacile`.

- [ ] **Step 2: Toggle + viste**

  `vista === "semplice"`: `EasyText` (se esiste) + blocchi di azione audio già presenti (`ClientPage.tsx:304-369`, spostati qui dentro); se non esiste e non sta semplificando: **banner CTA verde** (`bg-green-50 border-green-200`, titolo «Versione facile da leggere», testo breve «Faccio una versione semplice e chiara del foglio illustrativo.») con pulsante grande «Genera la versione facile» (stesso handler `semplifica()`) + sotto, il `OriginalDocument` **in un `<details>` collassato** «Vedi anche il foglio originale» (così la pagina non è mai vuota).
  `vista === "originale"`: solo `OriginalDocument` (a larghezza piena, `max-w-3xl mx-auto`).
  Durante `semplificando`: skeleton/attesa dentro la vista Semplice (il Task 7 sostituirà lo spinner con lo skeleton; per ora mantenere il blocco attesa esistente `ClientPage.tsx:283-293`).

- [ ] **Step 3: Auto-caricamento (Review Focus 2 e 5)**

  Nel `useEffect` di caricamento (`ClientPage.tsx:50-130`), dopo il fetch di farmaco+documento: se `versioneGiaGenerata(farmacoId)` → chiamare `semplifica()` una volta. In `semplifica()` (`ClientPage.tsx:132-155`), dopo `setVersioneFacile(versione)` di successo → `registraVersioneGenerata(farmacoId)`. Se il registro non contiene il farmaco (anche con cache backend calda): nessuna chiamata automatica, resta il CTA.

- [ ] **Step 4: Chat e scenario come drawer**

  ChatPanel: spostare da colonna grid a drawer sovrapposto — wrapper `fixed inset-y-0 right-0 z-30 w-full sm:max-w-md bg-white shadow-xl border-l border-gray-200` con backdrop `fixed inset-0 bg-black/30 z-20` che chiude al click; visibile solo con `chatOpen`. Contenuto del drawer: `ChatPanel` (richiede `isOpen` come ora) con header interno già suo; aggiungere area `pt-14` se ChatPanel non ha margine per non finire sotto lo sticky header. `ScenarioWizard` resta modal com'è (già overlay).

- [ ] **Step 5: Commute da fonte citata (Review Focus 3 e 4)**

  In `evidenziaFonte` (`ClientPage.tsx:45-48`) aggiungere `setVista("originale")`; nel parsing `?fonte=` (righe 105-123) aggiungere `setVista("originale")` quando il blocco viene trovato.

- [ ] **Step 6: Verifica lint + build**

  Run: `cd frontend && npm run lint && npm run build`
  Expected: nessun errore; niente warning di idratazione.

- [ ] **Step 7: Verifica manuale dei flussi**

  Con backend attivo (`make backend`, `npm run dev`):
  1. Storage pulito → apri farmaco mai generato: banner CTA verde + foglio in `<details>`; click genera (~30 s) e poi `EasyText` appare; registro aggiornato.
  2. Reload stesso farmaco: versione facile appare da sola (cache-hit, veloce).
  3. `?fonte=<id blocco valido>` dalla modalità guidata: si apre su Originale col blocco in evidenza.
  4. Chat: apre drawer, la pagina dietro non salta; citazione chat → vista commuta su Originale col blocco evidenziato.
  5. Toggle Semplice/Originale funzionante in entrambe le direzioni; 🔊 e Guidami operativi; voci di `PiuMenu` (scenario, condividi, rigenera, chat) operativi.
  6. Storage bloccato: pagina rende, CTA verde appare, nessun errore console (Review Focus 2).

- [ ] **Step 8: Commit**

  ```bash
  git add frontend/src/app/farmaco/[id]/ClientPage.tsx
  git commit -m "feat(ui): pagina farmaco con gerarchia, toggle viste e auto-caricamento da registro locale"
  ```

### Task 6: Flash animato sulla fonte citata

**Files:**
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/components/OriginalDocument.tsx` (blocco attivo, righe ~65-84)

**Interfaces:**
- Consumes: `focusNonce` prop già esistente (incrementato da `evidenziaFonte` e dal parsing `?fonte=`).
- Produces: classe CSS globale `fc-flash` (keyframes `fc-flash`: `background` da `#fef08a` opacità piena a trasparente, `1.5s ease-out`, una volta sola) utilizzabile da qualunque componente.

- [ ] **Step 1: Keyframes in `globals.css`**

  ```css
  @keyframes fc-flash {
    from { background-color: rgba(254, 240, 138, 0.9); }
    to   { background-color: transparent; }
  }
  .fc-flash { animation: fc-flash 1.5s ease-out 1; }
  ```

- [ ] **Step 2: Applicare al blocco attivo**

  In `OriginalDocument.tsx`: il `div` del blocco attivo (riga ~68) aggiunge `fc-flash` alla className quando `attivo`; la classe si ri-applica a ogni nuovo focus usando `key={blocco.blocco_id + "-" + focusNonce}` sul div attivo (remonta l'elemento e riparte l'animazione). Il `bg-yellow-50 ring-1 ring-yellow-200` statico resta come stato persistente dopo il flash.

- [ ] **Step 3: Verifica lint + build**

  Run: `cd frontend && npm run lint && npm run build`
  Expected: nessun errore.

- [ ] **Step 4: Verifica manuale (Review Focus 4)**

  Chat → citazione: blocco lampeggia giallo ~1,5 s poi resta con evidenza soft; seconda citazione → il flash riparte. `prefers-reduced-motion`: aggiungere in `globals.css` `@media (prefers-reduced-motion: reduce) { .fc-flash { animation: none; } }` e verificarlo in DevTools (emulazione).

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/app/globals.css frontend/src/components/OriginalDocument.tsx
  git commit -m "feat(ui): flash animato sul blocco citato nel foglio originale"
  ```

### Task 7: Skeleton loader

**Files:**
- Create: `frontend/src/components/Skeleton.tsx`
- Modify: `frontend/src/app/farmaco/[id]/ClientPage.tsx` (solo blocco loading, righe ~161-173)

**Interfaces:**
- Produces:
  ```ts
  export function Skeleton({ className }: { className?: string })
  ```
  `div` con `animate-pulse bg-gray-200 rounded` + `className` passata. (Tailwind `animate-pulse` esiste già, niente keyframes custom.)

- [ ] **Step 1: Implementare `Skeleton` e sostituire lo spinner**

  Nel loading di `ClientPage` (`ClientPage.tsx:161-173`): sostituire spinner + testo con skeleton che replica la struttura del mockup `dettaglio-p3.html` (A): card con barra titolo, 3-4 righe di testo, 2 bottoni fittizi. Mantenere il messaggio accessibile visivamente-nascosto «Sto caricando il foglio illustrativo…» (`sr-only` + `aria-busy="true"` sul contenitore).

- [ ] **Step 2: Verifica lint + build**

  Run: `cd frontend && npm run lint && npm run build`
  Expected: nessun errore.

- [ ] **Step 3: Verifica manuale**

  Throttle network a "Slow 3G" in DevTools, aprire un farmaco: skeleton visibile, poi contenuto reale; `aria-busy` presente nel DOM durante il caricamento.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/components/Skeleton.tsx frontend/src/app/farmaco/[id]/ClientPage.tsx
  git commit -m "feat(ui): skeleton loader al caricamento della pagina farmaco"
  ```

### Task 8: Toast di conferma

**Files:**
- Create: `frontend/src/components/Toast.tsx`
- Modify: `frontend/src/app/farmaco/[id]/ClientPage.tsx`

**Interfaces:**
- Produces:
  ```ts
  interface ToastProps {
    messaggio: string
    onChiuso: () => void
  }
  export function Toast(props: ToastProps)
  ```
  Fixed bottom-center, `bg-gray-900 text-white text-sm rounded-lg px-4 py-2.5 shadow-lg`, `role="status"`, auto-dismiss 3 s con `useEffect` + `setTimeout` (pulito nel cleanup), transizione fade-in via Tailwind.

- [ ] **Step 1: Implementare `Toast`**

- [ ] **Step 2: Collegare i due messaggi in `ClientPage`**

  Stato `toast: string | null`. Due trigger: TTS pronto a suonare (dove oggi `ttsLoading` diventa falso senza `ttsError`, messaggio «Audio pronto») e generazione versione facile completata (in `semplifica()` dopo successo, messaggio «Versione facile generata» — o «Versione già disponibile» se `versione.cached`). Un solo `Toast` montato alla volta.

- [ ] **Step 3: Verifica lint + build**

  Run: `cd frontend && npm run lint && npm run build`
  Expected: nessun errore.

- [ ] **Step 4: Verifica manuale**

  Generare versione facile → toast compare, sparisce da solo dopo 3 s, `role="status"` nel DOM. Audio pronto → toast. Nessun toast in caso di errore (gli errori restano nei blocchi `role="alert"` esistenti).

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/Toast.tsx frontend/src/app/farmaco/[id]/ClientPage.tsx
  git commit -m "feat(ui): toast di conferma per audio e generazione versione facile"
  ```

### Task 9: Sweep palette + verifica finale

**Files:**
- Modify: `frontend/src/app/scheda/[id]/ShareCard.tsx` (accenti palette, leggere)
- Modify: `frontend/src/components/ChatPanel.tsx` (solo bordo/accents, logica intatta)

**Interfaces:**
- Consumes: palette da Global Constraints. Nessun'altra interfaccia cambia.

- [ ] **Step 1: Applicare la palette**

  `ShareCard.tsx`: titolo/accents in verde (versione facile condivisa) con bordo `green-200`; `ChatPanel.tsx`: bordo superiore/accent blu (approfondimento). Niente ristrutturazioni: solo classi colore. Se un file usa già i colori giusti, non toccarlo.

- [ ] **Step 2: Verifica lint + build**

  Run: `cd frontend && npm run lint && npm run build`
  Expected: nessun errore.

- [ ] **Step 3: Checklist finale completa (Review Focus) + `make test`**

  Run: `make test` (backend pytest + frontend lint)
  Expected: tutto verde. Poi ripassare manuale i 5 punti del Review Focus: (1) ricerca con backend fermo → errore visibile; (2) storage bloccato → home e pagina farmaco rendono; (3) `?fonte=` → parte su Originale; (4) citazione chat su vista Semplice → commuta con flash; (5) registro locale vuoto → CTA, mai auto-generazione. Più: modalità guidata (`/farmaco/<id>/guida`) invariata (testo grande, alto contrasto, TTS), scheda condivisa (`/scheda/<id>`) leggibile.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/app/scheda/[id]/ShareCard.tsx frontend/src/components/ChatPanel.tsx
  git commit -m "feat(ui): sweep palette verde/blu/ambra su scheda condivisa e chat"
  ```
