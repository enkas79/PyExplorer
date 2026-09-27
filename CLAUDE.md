# Guidelines per Claude Code

## 1. Stack e Contesto Principale
* **Linguaggio Principale:** Python 3.9+ (Focus assoluto, type hints PEP 484 obbligatori, standard OOP).
* **Framework GUI:** Esclusivamente **PyQt6** o **PySide6** (Non usare Tkinter, CustomTkinter, Flet o altri framework).
* **Controllo Versione & CI/CD:** GitHub Actions (Build ed esecutabili multi-piattaforma generati da PyInstaller / NSIS).
* **Linguaggi Secondari (uso RARO):** PHP, JavaScript, Java. Usali solo se esplicitamente richiesto per integrazioni esterne.

## 2. Componenti Obbligatori dell'Interfaccia (GUI)
* **Barra dei Menu (`QMenuBar`):** Ogni finestra principale dell'applicazione deve includere una barra dei menu strutturata con:
  * **Menu "Aiuto" / "Info":**
    * **Informazioni / About:** Finestra di dialogo (`QMessageBox.about`) contenente l'autore dell'applicazione e la versione corrente letta dinamicamente dal file `version.txt`.
    * **Controlla Aggiornamenti:** Voce di menu per avviare manualmente la verifica e il download di nuove versioni disponibili.
    * **Guida:** Voce che apre una finestra dedicata o un dialogo informativo con la guida all'uso dell'applicazione.
  * Altre voci di menu verranno specificate di volta in volta secondo le necessità del progetto.

## 3. Gestione Versioni, Release & Autoupdate
* **File di Versione:** Il file `version.txt` situato nella root del progetto contiene il numero di versione corrente (es. `1.0.0`).
* **Trigger di Build:** Ogni volta che si apportano modifiche, fix o nuove funzionalità ai file di codice, **aggiorna sempre il numero di versione in `version.txt`** (incrementando patch o minor). Questo scatena automaticamente la build degli installer via `.github/workflows/build-installers.yml`.
* **Sistema di Autoupdate:**
  * **Verifica Automatica all'Avvio:** L'applicazione deve verificare in background (tramite API GitHub Releases o endpoint dedicato) la presenza di nuove versioni confrontando la versione remota con quella locale in `version.txt`.
  * **Notifica e Download:** Se disponibile una nuova release, mostrare un dialogo informativo (`QMessageBox` o dialogo custom con changelog) chiedendo conferma all'utente.
  * **Installazione / Sostituzione:** Gestire il download dell'installer/binario aggiornato ed eseguire il processo di aggiornamento/riavvio senza bloccare l'esperienza utente.

## 4. Standard di Sviluppo GUI & Architettura Qt
* **Threading/Asincronia:** NON eseguire mai operazioni I/O, chiamate API di rete, query pesanti o controllo aggiornamenti nel main thread della GUI. Usa sempre `QThread` (o `QThreadPool`/`QRunnable`) e i segnali (`pyqtSignal` / `Signal`) per comunicare con l'interfaccia.
* **Separazione Architetturale:** Separa rigorosamente la logica della GUI (layout, widget, segnali) dalla logica di business/backend e dal modulo di aggiornamento (`updater`).
* **Design & Styling (QSS):**
  * Applica griglie di spaziatura coerenti (multipli di 4px/8px per padding e margini).
  * Palette coerenti ad alto contrasto (WCAG AA compliant) per temi scuri/chiari, evitando gradienti casuali o pulsanti disallineati.
  * Nessun elemento UI deve sembrare un widget di sistema grezzo non stilizzato: usa fogli di stile centralizzati (`styles.qss` o modulo dedicato).
* **Gestione Errori:** Intercetta le eccezioni di rete o I/O silenziosamente in background o tramite dialoghi chiari (`QMessageBox.warning`/`QMessageBox.critical`) se l'azione è manuale, impedendo qualsiasi crash improvviso.

## 5. Comandi di Sviluppo & Test
* **Esecuzione App:** `python src/main.py`
* **Test Suite:** `pytest` (priorità alla logica interna e modelli)
* **Linter / Formatting:** `ruff check . --fix` (in alternativa `black .` / `flake8 .`)
* **Dipendenze:** `pip freeze > requirements.txt`

## 6. Regole Operative per l'Agente
* **Lingua:** Rispondi e inserisci commenti nel codice sempre in **italiano**.
* **Stile Risposte:** Diretto, asciutto, orientato al codice e ai comandi. Evita preamboli e conclusioni superflue.
* **Autonomia e Versionamento:** Aggiorna `version.txt` a ogni modifica funzionale o strutturale.
* **Gestione Git e Branch:** Completate e verificate le modifiche su un branch, esegui autonomamente push e merge su `main` senza richiedere conferme ridondanti.
* **Pulizia Workspace:** Non generare file `.md` effimeri di recap, note sparse o copie `.bak` se non espressamente richiesto.

## 7. Integrazione Plugin, Skill & Server MCP

### Strumenti Attivi e Obbligatori:
* **claude-mem:** Salva contesto, bug risolti e decisioni architetturali direttamente nella memoria del plugin tra una sessione e l'altra (`mem-search`, `learn-codebase`).
* **superpowers:**
  * Applica `test-driven-development` per moduli core e logica di business.
  * Usa `systematic-debugging` in caso di bug o crash Qt.
  * Prima di modifiche strutturali, stila il piano d'azione (file target, segnali/slot, thread worker).
* **impeccable & frontend-design:**
  * Applica le loro regole di design system, accessibilità, proporzioni e palette esclusivamente a **QSS (Qt Style Sheets)** e layout PyQt/PySide.
  * Vietata l'introduzione di dipendenze o runtime web (HTML/CSS grezzo non interpretato da Qt).
* **21st-ui:**
  * Usalo solo per ricercare riferimenti visivi, layout di card, sidebar o tabelle moderne.
  * Traduci i pattern trovati direttamente in widget Qt e classi QSS corrispondenti.
* **Context7:**
  * Interrogalo per verificare firme esatte di metodi, enumerazioni o differenze tra versioni di PyQt6/PySide6 prima di ipotizzare API deprecate o inesistenti.

### Strumenti Esclusi (Blacklist):
* **Ignora categoricamente:** Plugin di contabilità/finanza (`variance-analysis`, `journal-entry`, `sox-testing`, ecc.), tool di editing Office (`docx`, `xlsx`, `pptx`) e comandi della suite **ponytail** (non forzare l'anti-pattern del minimalismo spinto a discapito della modularità OOP e della robustezza del codice).