# Design — Revisione UX del frontend di Farmaco Chiaro

Data: 2026-11-14
Stato: approvato dall'utente (mockup validati nel companion visivo)
Mockup di riferimento: `docs/superpowers/specs/2026-11-14-ux-mockups/`
(`proposte-overview.html`, `dettaglio-p1-p2.html`, `dettaglio-p3.html` —
frammenti HTML autentici validati dall'utente, contengono testi e layout)
Prossimo passaggio: piano di implementazione (superpowers:writing-plans)

## Intento e perché

Il frontend (Next.js App Router + Tailwind, `frontend/src/`) è funzionale ma
"piatto": la home dà solo la barra di ricerca, la pagina farmaco offre 6
comandi alla pari senza gerarchia e nasconde il frutto principale dell'app
(versione facile) dietro un click manuale su "Semplifica testo". Obiettivo:
rendere la navigazione più accattivante e guidare l'utente verso la versione
facile, mantenendo l'accessibilità già buona della modalità guidata
(testo grande, alto contrasto, TTS, focus management).

## Obiettivi / non-obiettivi / anti-obiettivi

**Obiettivi**

1. Home che accoglie: farmaci comuni, ricerche recenti, ricerca che risponde
   anche a vuoto.
2. Pagina farmaco con gerarchia: un'azione primaria per schermata, versione
   facile subito disponibile, comandi secondari raggruppati.
3. Feedback visivo coerente: skeleton loader, flash sulla fonte citata,
   palette condivisa verde/blu/ambra su tutte le schermate.

**Non-obiettivi**

- Nessun cambio di logica backend/API (FastAPI in `backend/` resta intatto).
- Nessuna riscrittura della modalità guidata (`GuidedMode.tsx`) né della
  scheda condivisa (solo applicazione della palette).
- Nessuna dark mode, nessuna nuova dipendenza di UI (resta Tailwind inline).

**Anti-obiettivi (cosa renderebbe il lavoro un fallimento)**

- Un restyling che peggiora l'accessibilità (contrast, focus ring, TTS,
  aria-* esistenti vanno preservati o migliorati, mai tolti).
- Meno chiarezza per l'utente anziano: la versione facile deve restare
  all'inizio del percorso, non sepolta.
- Un'esperimento costoso: la versione facile NON va generata automaticamente
  a ogni apertura pagina se non in cache (costo AI); solo cache-hit = auto.

## Vincoli

- Il backend espone già `simplify` con flag `cached` nella risposta
  (`SimplifyResponse.cached`): l'auto-caricamento si basa su questo flusso,
  nessuna nuova API.
- La lista "Più cercati" sarà una lista curata hardcoded nel frontend
  (costante in `frontend/src/lib/`): nessuna telemetria o endpoint nuovo.
  Un endpoint di analytics è un'eventuale estensione futura, fuori scope.
- "Ricerche recenti" in `localStorage` (massimo 3, solo su dispositivo
  utente, con nota "solo sul tuo dispositivo" nella UI).
- Next.js versione recente: consultare `node_modules/next/dist/docs/` prima
  di scrivere codice di routing/Client Components.

## Approcci considerati

1. **Solo home (porta d'ingresso)** — la meno invasiva, ma non risolve la
   pagina dove l'utente passa più tempo. Scartata come opzione unica.
2. **Solo pagina farmaco** — il massimo dell'impatto ma accoglia male
   l'utente nuovo. Scartata come opzione unica.
3. **Tutte e tre combinate, in sequenza** *(scelta dell'utente)* —
   1 accoglie, 2 struttura, 3 rifinisce. L'utente ha validato i mockup di
   tutte e tre nel companion visivo.

## Design delle tre parti

### Parte 1 — Home porta d'ingresso (`app/page.tsx`, `SearchBar.tsx`)

- Hero centrato con gradiente azzurro leggero, titolo, claim.
- Sotto la ricerca: chip "Più cercati" (lista curata costante, click =
  naviga direttamente alla pagina farmaco) e riga "Ricerche recenti"
  (localStorage, max 3, cancellabile).
- Le tre voci di "Come funziona" diventano card affiancate con icone di
  `lib/icone.ts` (📖 Trova · ✅ Leggi facile · 🔊 Ascolta/Chiedi).
- **Ricerca senza risultati: empty state esplicito.** In `SearchBar.tsx`
  oggi `isOpen` resta false se `risultati.length === 0`: il dropdown non si
  apre e l'utente non capisce se è un errore. Nuovo comportamento: dropdown
  aperto anche a vuoto, con messaggio "Non ho trovato «query»" + suggerimento
  di provare il principio attivo (es. Tylenol → paracetamolo). Stato di
  errore di rete distinto dal "nessun risultato".

### Parte 2 — Pagina farmaco con gerarchia (`farmaco/[id]/ClientPage.tsx`)

- Header ridisegnato: "← torna" + nome + principio attivo; sotto, una riga
  con **toggle segmentato [Semplice | Originale]** (stato locale, default
  "Semplice"), pulsante 🔊 ascolta, CTA "🧭 Guidami" (primario, blu), menu
  "⋯" che raccoglie: Chat, "Cosa faccio se…?", Condividi, Rigenera.
- **Niente più due colonne affiancate di default:** il toggle sostituisce le
  due colonne (oggetti `OriginalDocument` ed `EasyText` restano componenti
  intatti; cambia solo chi viene mostrato). Su schermi larghi (lg+) la vista
  "Originale" può affiancare la versione facile tramite un piccolo controllo
  opzionale "Affianca" — scoperta del builder, non è un requisito.
- **Versione facile auto-caricata (deciso con l'utente):** all'apertura
  pagina si consulta un registro locale in `localStorage` dei farmaci di cui
  l'utente ha già generato la versione facile. Se il farmaco è nel registro,
  si chiama `simplify` una volta (cache-hit, risposta immediata) e si mostra
  subito; dopo ogni generazione riuscita il registro si aggiorna. Se non è
  nel registro, si mostra il CTA unico evidente "Genera la versione facile"
  (non più l'avviso ambra di testo puro): la prima generazione resta sempre
  un click esplicito — mai una generazione AI involontaria né un'attesa di
  ~30 s non richiesta. Limitazione accettata: il registro è per dispositivo,
  quindi un farmaco generato su un altro dispositivo richiede un click
  anche se la cache backend lo contiene.
- L'evidenziazione della fonte via `?fonte=<blocco_id>` deve continuare a
  funzionare: quando un blocco è citato da chat/guida/scenario, la vista si
  porta su "Originale" automaticamente con quel blocco in evidenza.

**Chiamate del designer su punti lasciati aperti dal builder check** (non
richiedono decisione dell'utente):

- **Chat e scenario nella vista a colonna singola:** si aprono come pannello
  sovrapposto (drawer laterale destro, sticky) che non ridistribuisce la
  pagina. Il contenuto letto non salta quando la chat si apre/chiude.
- **Vista "Semplice" prima della prima generazione:** la vista Semplice non
  resta quasi vuota: mostra il banner CTA verde "Genera la versione facile"
  e, sotto, il foglio originale collassato ma accessibile (l'utente vede
  che c'è contenuto, non una pagina vuota). Con la versione facile presente,
  il foglio originale resta disponibile dal toggle "Originale".
- **Lista "Più cercati":** il builder la cura dal dataset reale
  (`backend/data`, verificando che gli id esistano e rispondano alla
  ricerca) invece di indovinare nomi di brand.

### Parte 3 — Micro-feedback e identità (componenti trasversali)

- **Skeleton loader** in `ClientPage` al primo caricamento (contorni delle
  card al posto dello spinner).
- **Flash sulla fonte:** in `OriginalDocument`, quando arriva una fonte
  (da chat, wizard o `?fonte=`), il blocco citato fa fade + flash giallo
  (~1,5 s) e scroll-into-view. Pure CSS/Tailwind, no dipendenze.
- **Palette sistematizzata:** verde = versione facile/lettura, blu =
  approfondire (chat, Guidami, "una frase"), ambra = situazioni reali
  (scenario, fonti, avvisi). Applicata a home, pagina farmaco, scheda
  condivisa, pannelli chat/scenario.
- Toast leggero di conferma per azioni lente completate (es. "Audio pronto",
  "Versione generata") — può essere un componente minimo inline, senza
  librerie esterne.

## Decisioni fatte (da mostrare all'utente per verifica)

1. Lista "Più cercati" hardcoded curata nel frontend (poi estendibile con
   analytics backend).
2. Versione facile: registro locale (localStorage) dei farmaci già
   generati; auto-caricamento solo per farmaci nel registro, prima
   generazione sempre su click esplicito (deciso con l'utente dopo il
   builder check: `POST /simplify` genera subito su cache-miss, non esiste
   una modalità di sola verifica).
3. Toggle Semplice/Originale al posto del layout a due colonne; affiancamento
   opzionale solo su schermi larghi, a discrezione del builder.
4. Ordine di implementazione: **1 → 2 → 3** (la 3 rifinisce le pagine
   già ristrutturate dalla 2).

## Stile visivo — "editoriale clinico" (ruling approvata dall'utente il 2026-11-14)

Aggiornamento (contatore, 2026-11-14): la home espone sotto la SearchBar una
fascia con il numero di farmaci disponibili (`TOTALE_FARMACI = 454`, costante
in `farmaci-comuni.ts` derivata dal dataset: 454 drug_id unici; il numero si
aggiorna manualmente insieme ai dati) e la nota «Il catalogo è in
aggiornamento: nuovi farmaci vengono aggiunti man mano.» — opzione A del
mockup `contatore-farmaci.html` convalidata dall'utente (fascia visibile sotto
la ricerca, non nel footer).

Dopo la validazione dei mockup l'utente ha chiesto un aspetto più
professionale e istituzionale e ha scelto lo stile C su tre proposte
(A portale navy, B teal moderno, C editoriale clinico), rifiutando le emoji
a favore di un set di icone vettoriali. Riferimento visivo autentico:
`docs/superpowers/specs/2026-11-14-ux-mockups/schermate-stile-c-iconset.html`
(tutte le schermate convalidate) e `stile-istituzionale.html` (le tre
proposte di stile). Regole vincolanti:

- **Superfici:** sfondo pagina `#fbfcfe`-like (gray-50/gray-[#fbfcfe]), card
  bianche con bordo sottile `gray-200`, raggio piccolo (rounded-sm/md),
  niente ombre pesanti (al massimo `shadow-sm`).
- **Identità:** header bianco con logo testuale "FARMACO**CHIARO**"
  (CHIARO in blu-600), etichette tecniche in maiuscolo con letter-spacing
  (`tracking-wider text-[10px] font-semibold uppercase`).
- **Accenti:** barra colorata verticale a sinistra dei contenuti chiave
  (blu-600 = approfondire, green-600 = versione facile, amber-500 = avvisi)
  al posto dei blocchi colorati pieni.
- **Azioni primarie:** link-azioni sottolineati in maiuscoletto con icona
  (es. «🔊 ASCOLTA», «🧭 GUIDAMI») con `border-bottom`; un solo bottone
  pieno per schermata al massimo (nero `bg-gray-900` per "AVANTI" nella
  guida).
- **Icone:** set Lucide a tratteggio 2px come componenti SVG inline in un
  unico modulo `frontend/src/components/Icone.tsx` — NESSUNA dipendenza npm
  (lucide-react non si installa: si copiano i path SVG necessari, licenza
  ISC, attributo `aria-hidden="true"`). Emoji eliminate dall'interfaccia
  (restano ammesse solo dove già usate come contenuti, non come icone UI).
- **Palette funzionale invariata:** verde = versione facile, blu =
  approfondire, ambra = situazioni reali.
- **Disclaimer AIFA** sempre visibile nelle pagine di contenuto.

## Cosa resta al builder

- Testi esatti delle card home e dell'empty state (bozze nel mockup).
- Micro-animazioni CSS e dettagli di Tailwind.
- Come raccogliere il menu "⋯" (dropdown semplice, nessuna libreria).
- Scelta dell'eventuale controllo "Affianca" su schermi larghi.

## Piano di verifica

- `make test` e lint del frontend verdi.
- Verifica manuale dei flussi: ricerca con esito, ricerca a vuoto, apertura
  pagina farmaco (cache e no), ?fonte= da guida, chat→flash, scenario→flash,
  TTS, alto contrasto/testo grande della modalità guidata invariati.
