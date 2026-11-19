# Intent: portare il repository su un SDLC AI-native

Autore: maintainer del progetto. Data: 2026-11-19. Stato: accettato.

## Problema

Il prodotto funziona, ma il processo che lo produce non è versionato né
ripetibile. Oggi:

- non esistono `intent`, `spec` e `plan` nel repository;
- gli agenti di progetto (`.opencode/agents/`) e la guida operativa non sono
  condivisi: `.opencode/` è in `.gitignore`;
- non esiste una policy di review (`REVIEW.md`) né un template di PR;
- la CI esegue test, lint e build, ma non verifica la configurazione
  dell'agente (prompt, skill, permessi) quando cambia;
- `REPORT.md` descrive una versione vecchia del sistema (ChromaDB, 5 farmaci,
  91 blocchi) mentre il codice usa Qdrant, 621 fogli e 169 test.

Il risultato è che la conoscenza vive nella testa del maintainer e nelle
sessioni degli agenti, non in artefatti che il prossimo cambiamento può
rileggere.

## Esito proposto

Il repository contiene e versiona:

1. una guida operativa per gli agenti (`AGENTS.md`, con `CLAUDE.md` come
   puntatore per Claude Code);
2. una policy di review (`REVIEW.md`) e un template di PR;
3. la catena `intent → spec → plan` per questo intervento, in
   `docs/ai-native/`;
4. due skill di progetto: sicurezza dei contenuti medici e workflow del
   cambiamento;
5. guardrail deterministici sui segreti, sugli artefatti generati e sulle
   azioni irreversibili (`opencode.jsonc`);
6. una eval di configurazione in CI che gira quando cambiano prompt, skill,
   agenti o artefatti del processo;
7. un audit onesto dei sei stadi del playbook, con ciò che resta fuori.

Riconoscimento del successo: un maintainer che non ha visto questa sessione
può aprire il repository, leggere `AGENTS.md` e `docs/ai-native/`, e produrre
un cambiamento con le stesse regole senza chiedere contesto.

## Utenti e sistemi toccati

- Maintainer e agenti che lavorano sul repository.
- CI GitHub Actions.
- Nessun cambiamento al comportamento del prodotto, alle API o ai dati.

## Vincoli

- Nessun cambio di comportamento per l'utente finale.
- Nessuna nuova dipendenza runtime.
- I test restano deterministici e offline (`RETRIEVAL_MODE=bm25`).
- Nessun segreto nel repository o negli artefatti.
- Non si riscrive l'architettura esistente: si estende dove il progetto ha
  già una convenzione.
- I contenuti medici restano vincolati al foglietto AIFA.

## Non-obiettivi

- Rate limiting, autenticazione e osservabilità degli endpoint LLM: sono il
  prossimo intervento (opzione C), con una sua spec.
- Refactor ampio di backend o frontend.
- Sostituzione di Qdrant, del modello o della pipeline di ingestion.
- Automazione completa del deploy o del loop di manutenzione: qui si
  documentano il gate e il rollback, non si automatizza la produzione.

## Domande aperte

1. Chi firma la revisione dei contenuti medici prima di un uso pubblico? Oggi
   è il maintainer; serve un farmacista o un medico per la produzione.
2. Si vuole abilitare una review automatica delle PR (Claude Code Action o
   servizio gestito)? Richiede un segreto e un budget; non è incluso qui.
3. Il prossimo intervento (hardening) va fatto prima o dopo un test di
   usabilità con utenti reali?
