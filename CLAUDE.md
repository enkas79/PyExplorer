# Guidelines per Claude Code

## 1. Stack e Contesto Principale
* **Linguaggio Principale:** Python 3.9+ (Focus assoluto).
* **Framework GUI:** Esclusivamente **PyQt6** o **PySide6** (Non usare Tkinter, CustomTkinter o altri framework).
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
* **Trigger di Build:** Ogni volta che si apportano modifiche, fix o nuove funzionalità ai file di codice, **aggiorna sempre il numero di versione in `version.txt`** (incrementando la versione patch o minor). Questo scatenerà automaticamente la build degli installer tramite il workflow `.github/workflows/build-installers.yml`.
* **Sistema di Autoupdate:**
  * **Verifica Automatica all'Avvio:** L'applicazione deve verificare in background (tramite API GitHub Releases o endpoint dedicato) la presenza di nuove versioni confrontando la versione remota con quella locale in `version.txt`.
  * **Notifica e Download:** Se è disponibile una nuova release, mostrare un dialogo informativo (`QMessageBox` o dialogo custom con changelog) chiedendo all'utente se desidera aggiornare.
  * **Installazione / Sostituzione:** Gestire il download dell'installer/binario aggiornato ed eseguire il processo di aggiornamento/riavvio senza bloccare l'esperienza utente.

## 4. Standard di Sviluppo GUI (Qt & Python)
* **Threading/Asincronia:** NON eseguire mai operazioni I/O, download, chiamate API di rete o controllo aggiornamenti nel thread principale dell'interfaccia. Usa sempre `QThread` (o `QThreadPool`/`QRunnable`) e i segnali (`pyqtSignal` / `Signal`) per notificare la GUI dell'esito dei controlli di update o dell'avanzamento dei download.
* **Separazione Architetturale:** Separa rigorosamente la logica dell'interfaccia grafica (layout, widget, segnali) dalla logica di business/backend e dal modulo di aggiornamento (`updater`).
* **Gestione Errori:** Intercetta le eccezioni di rete o di I/O (es. assenza di connessione durante l'autoupdate) silenziosamente in background o tramite dialoghi chiari (`QMessageBox.warning`/`QMessageBox.critical`) se l'aggiornamento è stato richiesto manualmente, senza far crashare l'applicazione.

## 5. Comandi di Sviluppo & Test
* **Esecuzione App:** `python src/main.py`
* **Test Suite:** `pytest`
* **Linter / Formatting:** `ruff check . --fix` (in alternativa `black .` / `flake8 .`)
* **Dipendenze:** `pip freeze > requirements.txt`

## 6. Regole Operative per l'Agente
* **Lingua:** Rispondi e inserisci commenti nel codice sempre in **italiano**.
* **Stile Risposte:** Sii sintetico e diretto. Vai subito al codice e ai comandi, evitando preamboli teorici o spiegazioni prolisse.
* **Autonomia e Versionamento:** Ricordati di aggiornare `version.txt` a ogni modifica rilevante ai file di progetto per garantire che la release su GitHub venga generata correttamente.
* **Gestione Git e Branch:** Una volta creato il branch e completate le modifiche, procedi direttamente al push/merge nel branch `main` in piena autonomia, senza richiedere conferme.
* **Pulizia Repo:** Non creare file spazzatura, note `.md` effimere o file di backup nel workspace a meno che non sia esplicitamente richiesto.

## 7. Integrazione Plugin & Skill Attive
* **claude-mem:** Salva contesto, bug risolti e decisioni architetturali direttamente nella memoria del plugin tra una sessione e l'altra. Non creare file markdown di riassunto nella repository.
* **superpowers:** Prima di toccare codice o widget esistenti, definisci sempre il piano d'azione (file target, segnali/slot, asincronia con QThread) e procedi all'implementazione una volta verificata la coerenza con l'architettura.
* **impeccable:** Applica i principi di design ed estetica visuale esclusivamente ai QSS (Qt Style Sheets), palette colori, spaziatura e tipografia dei componenti PyQt/PySide, evitando l'introduzione di pattern o tecnologie web.
* **task-observer:** Monitora le correzioni e i workflow eseguiti per raffinare i comandi futuri senza richiedere conferme o generare log ridondanti.
* **OmniRoute:** Se configurato come proxy per il fallback o modelli esterni, mantieni la compatibilità con le chiamate e le variabili d'ambiente standard definite.
