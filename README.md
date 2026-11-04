# 🌊 ComputerFlow

Ein lokaler Sprach- und Bildschirmassistent für den Desktop im frühen Entwicklungsstadium.

> „Computer, wechsle auf den Twitch-Tab von Papaplatte.“

**Stand 0.0.2.** Der experimentelle Windows-x64-Stand ergänzt die ersten geprüften Desktopaktionen um freihändige Sprachsteuerung. Nachweise und Grenzen stehen im [Prüfbericht](docs/VALIDATION.md).

## Implementiert für 0.0.2

- „Computer“ und Auftrag in einem Satz sprechen. Ein RAM-Ringpuffer hält den Satzanfang vor. Empfindlichkeit und Sprachende sind einstellbar.
- PTT mit rechter Strg-Taste halten und loslassen. Tastatur- und Maustasten sowie Umschaltmodus sind konfigurierbar. PTT und Wake Word lassen sich einzeln oder gemeinsam aktivieren.
- „Stopp“ oder „Abbrechen“ unterbricht einen laufenden Auftrag oder die Sprachausgabe. Kurze Töne markieren Aktivierung und einfache Erfolge. Rückfragen, Übungsfreigaben und Fehler spricht die lokale deutsche Windows-Stimme.
- Freiwillige, löschbare Stimmprüfung für Wake-Aufträge und optionale vorübergehende Lautstärkeabsenkung anderer Wiedergabequellen.
- Ein Auftrag führt höchstens eine Aktion aus: sichtbares Fenster fokussieren, Systemlautstärke auf 0–100 % setzen oder eine eindeutig adressierte Windows-Mediensitzung abspielen/pausieren.
- Lokale Audio-/Textaufträge über llama.cpp: offizielle ASR-Aufgabe, danach schemaerzwungene Aktionsplanung. Zielnamen werden unabhängig vom Modell eindeutig an den aktuellen Kontext gebunden. Strikte Validierung, höchstens eine Formatkorrektur, kein Mock-Modus im Produkt.
- Eigene Serververwaltung: fest versionierte Downloads mit SHA-256-Prüfung, fortsetzbare Downloads, Vulkan-Geräteprüfung, sichtbarer CPU-Fallback und Start/Status/Stop. Standard: `127.0.0.1:47831`, zufälliger API-Schlüssel, keine Shell-Tools im Modellserver.
- Unabhängiger Not-Aus **Strg+Alt+Escape**, Auftragsdeadline, Verwerfen verspäteter Antworten und Unterbrechung bei Vordergrundwechsel während Planung/Freigabe. **Strg+C** beendet das Programm.
- Konsolenstatus, Fehlerdiagnose, RAM-Sitzungsverlauf und Rückfragen per nächster PTT-Aufnahme. Übungsmodus zeigt die konkrete Aktion; **F6** gibt genau diese Aktion zeitlich begrenzt frei.
- Sichtbare Mikrofonauswahl beim ersten interaktiven Start und jederzeit über `-Microphone`; die Auswahl wird nach Gerätename und Host-API gespeichert. Beim Sprechen zeigt die Konsole die erkannte Anweisung.
- Fensterzuordnung nach Programmnamen, Prozess und Fenstertitel. Ein eindeutiger Kurzname wie „Steam“ kann auch zu einem längeren Windows-Produktnamen passen. Bei mehreren passenden Fenstern fragt ComputerFlow nach.
- Native Zustandsprüfung nach Systemaktionen. Fehlende Fähigkeiten und nicht bestätigte Ergebnisse werden gemeldet; fehlgeschlagene Aktionen werden nicht blind wiederholt.

Windows kann Fokuswechsel aus Hintergrundprozessen sperren. In diesem Fall meldet ComputerFlow den Wechsel als nicht bestätigt; globale Windows-Fokuseinstellungen werden nicht verändert.

Screenshots, UI-Bedienung, Tray, Web-Panel, Installer und weitere Plattformadapter folgen den späteren Meilensteinen.

## Ziel und Arbeitsweise

ComputerFlow soll Sprache, Fensterinformationen und bei Bedarf Bildschirmbilder zu ausführbaren Desktop-Aufträgen verbinden. Die Verarbeitung bleibt lokal. Windows wird zuerst umgesetzt; Linux und macOS bleiben Teil des Zielumfangs. Unterschiedliche Hardware wird über Plattformadapter, automatische Auswahl und Geräteprofile berücksichtigt.

Wir beginnen mit Push-to-Talk und ergänzen das Wake Word unmittelbar danach. Tests begleiten die Umsetzung; eine separate vorgeschaltete Modelltestphase entfällt.

## Beschlossener Zielumfang

Die folgende Liste beschreibt das Gesamtziel, nicht den aktuellen Implementierungsstand.

- **Audio:** Rechte Strg-Taste halten als PTT-Standard, freie Belegung und Umschaltmodus optional. Austauschbares „Computer“-Wake-Word-Modell, Ringbuffer und anpassbare Sprachende-Erkennung. Persönliche Stimmerkennung optional und standardmäßig aus.
- **Bedienung:** Direkte Schnittstellen → Accessibility → visuelle Erkennung. Mehrstufige Aufträge mit Zustands- und Erfolgskontrolle, Mehrmonitorbetrieb, unterschiedliche Skalierungen und Unicode-Texteingabe.
- **Bildschirm:** Bilder selbstständig bei Bedarf nachholen, Fenster- und Zeigekontext berücksichtigen. SoM als bedarfsgesteuerte Erkennungshilfe und kurze, abschaltbare Zielvorschau vor visuellen Klicks.
- **Browser:** Grundbedienung ohne Erweiterung. Erste optionale Erweiterung für **Firefox**, andere Browser später.
- **Modell:** Zunächst LFM3-Omni-2B über einen lokalen llama.cpp-Server. Austauschbare Modell-/Backendadapter und streng geprüftes internes Aktionsformat. Automatische Hardware-/Quantisierungsauswahl, manuelle Kontrolle und sichtbarer CPU-Fallback.
- **Sicherheit:** Alltagsaktionen direkt; konkrete Bestätigung vor Senden, Kaufen, Löschen, Verwerfen von Änderungen und sensiblen Einstellungsänderungen. Freigabe und Abbruch per Sprache und Panel. Not-Aus, Laufzeitgrenzen und kontrollierte Fehlerbehandlung. Shell-Zugriff bleibt auch über Aktionskombinationen ausgeschlossen.
- **Datenschutz:** Audio/Bilder standardmäßig flüchtig. Sitzungsverlauf und begrenztes Kurzzeitgedächtnis. Dauerhafte Historie, Debug-Aufnahmen und gespeicherte Testfälle nur nach Zustimmung, begrenzt und löschbar. Aufnahme-Ausschlüsse.
- **Rückmeldung:** Lokale Sprachausgabe standardmäßig knapp; still und gesprächig wählbar. Rückfragen bei Mehrdeutigkeit, unterbrechbare eigene Audioausgabe und optionale Lautstärkeabsenkung.
- **Oberfläche:** Tray, geschütztes lokales Web-Panel, geführte Einrichtung, Geräteprofile und Übungsmodus.
- **Aufträge:** Diktieren, Bildschirminhalte vorlesen/erklären, gezielte Mediensteuerung, genaue Lautstärke, Programm-Aliase, Makros/Szenen mit Import/Export.
- **Erweiterbarkeit:** Aktivierbare Plugins und freiwillige Fehlerkorrekturen als lokale Regressionstestfälle. Community-Installation, automatisches Modelltraining und portable Ausgabe sind spätere Ausbauten.

## Geplanter Ablauf

Sprache → Kontext beschaffen → Modelladapter → typisierte Aktion → Ziel-/Richtlinienprüfung → gegebenenfalls Bestätigung → Plattform/Integration → Ergebnis prüfen → fortsetzen, nachfragen oder abschließen.

Bedarfsgesteuerte Verarbeitung darf keine stillschweigend fehlenden Funktionen erzeugen. ComputerFlow beschafft fehlenden Kontext oder fragt nach. Nicht verfügbare Fähigkeiten und fehlgeschlagene Schritte werden sichtbar gemeldet.

## Roadmap

Die vollständige **[Roadmap](ROADMAP.md)** beginnt bei **0.0.1**. Sie beschreibt größere nutzbare Etappen auf einem langen Weg zu 1.0. Versionsnummern sind Planungsziele und noch keine Releases.

| Zielversion | Ergebnis |
|---|---|
| 0.0.1 | Lokaler Windows-Durchstich mit Push-to-Talk und ersten Systemaktionen |
| 0.0.2 | Wake Word „Computer“ und alltagstaugliche Audioaufnahme |
| 0.0.3 | Geprüfte Desktop- und UI-Bedienung |
| 0.0.4 | Optionale Firefox-Anbindung |
| 0.0.5 | Panel, Einrichtung und Geräteprofile |
| 0.0.6 | Diktieren, Bildschirmassistenz und Folgeaufträge |
| 0.0.7 | Makros und erweiterbare Integrationen |

Spätere 0.x-Stände vertiefen Alltagstauglichkeit, Verteilung, Browser- und Betriebssystemunterstützung. 1.0 erhält bewusst noch keinen Termin.

## Einrichtung unter Windows

Voraussetzungen: Windows x64, Python 3.11–3.14, [uv](https://docs.astral.sh/uv/), interaktiver Desktop mit Mikrofonfreigabe und beim ersten Einrichten Internetzugang für rund 1,6 GB geprüfte Downloads. Laufzeit und Modelle werden von ComputerFlow eingerichtet; eine vorhandene llama.cpp-Installation ist nicht nötig.

```powershell
.\Start-ComputerFlow.ps1
```

Das Startskript richtet Python-Abhängigkeiten und Modellgewichte im Programmordner ein und startet den Assistenten. `setup` installiert **llama.cpp b11960**, **LFM3-Omni-2B Q4_K_M**, den **Q8_0-Vision-/Audioprojektor** und das deutsche Vosk-Modell **small-de-0.15** für „Computer“ und Sprachstopp. [Gepinnte Downloads und Prüfsummen](src/computerflow/runtime/artifacts.py), [GGUF-Modellkarte](https://huggingface.co/LiquidAI/LFM3-Omni-2B-GGUF), [Vosk-Modellkatalog](https://alphacephei.com/vosk/models)

```powershell
.\Start-ComputerFlow.ps1 -Setup       # Nur einrichten / Dateien erneut prüfen
.\Start-ComputerFlow.ps1 -Doctor      # Server starten und Diagnose anzeigen
.\Start-ComputerFlow.ps1 -StopServer  # Eigenen Modellserver beenden
.\Start-ComputerFlow.ps1 -Microphone  # Webcam/Headset auswählen und speichern
.\Start-ComputerFlow.ps1 -Speaker enroll # Freiwillige Stimmprüfung einrichten
.\Start-ComputerFlow.ps1 -Speaker status
.\Start-ComputerFlow.ps1 -Speaker delete
```

Ohne gespeicherte Auswahl fragt der erste interaktive Start nach dem Aufnahmegerät. Die Auswahl gilt nur für ComputerFlow. Windows-Standardgeräte werden dadurch nicht umgestellt. Bei fehlendem oder mehrdeutigem gespeichertem Gerätenamen erscheint eine Fehlermeldung mit dem Auswahlbefehl statt eines stillen Wechsels zum Headset. Die CLI bietet zusätzlich `microphone --list` und `microphone --select ID`.

Der Server startet unsichtbar im Hintergrund und bleibt für Folgeaufträge verfügbar. Er bindet ausschließlich die konfigurierte numerische Loopback-Adresse. Der eigene Standardport **47831** vermeidet typische Konflikte mit lokalen Diensten auf 8080; vor dem Start wird die Belegung geprüft. Ein fremder Prozess wird weder übernommen noch beendet. Der zufällige API-Schlüssel liegt nur in der privaten lokalen Serverzustandsdatei und wird nicht in URLs, Konsole oder Prozessargumente geschrieben. Ein Standardport oder dessen Vermeidung ersetzt diesen Zugriffsschutz nicht.

`runtime.acceleration` erlaubt `auto`, `vulkan` oder `cpu`. Mit `runtime.device` lässt sich ein erkanntes Vulkan-Gerät wählen. Nach einer Hardwareänderung den Server stoppen und erneut starten.

### Datenordner

Im Programmordner liegt `config.yaml`. Das Unterverzeichnis `.computerflow/` bündelt Modelle, Laufzeit, Downloadarchive, Geräteprofil, Serverzustand, uv-Cache, temporäre Dateien und die vom Startskript eingerichtete Python-Umgebung. Ein abweichendes `runtime.data_dir` muss innerhalb des Programmordners liegen. Für ein aus dem Wheel installiertes Programm lässt sich der Programmordner mit `COMPUTERFLOW_HOME` festlegen. Ohne diese Angabe verwendet das Wheel `ComputerFlow/` unter seiner Python-Umgebung.

Für den Umstieg von 0.0.1 mit eigenem Datenpfad zuerst den alten ComputerFlow-Server mit der alten Version beenden. `models/` und `downloads/` aus dem bisherigen Datenordner in `.computerflow/` kopieren, `runtime.data_dir` in `config.yaml` auf `null` setzen und `Start-ComputerFlow.ps1 -Setup` ausführen. Das Setup prüft die kopierten Dateien und erstellt das Installationsprofil am neuen Ort. Nach erfolgreicher Diagnose kann der alte ComputerFlow-Datenordner entfernt werden.

Bei einem Programmordner in OneDrive können die normalen Programmdateien und Modelle synchronisiert werden. Server-Schlüssel und optionales Stimmprofil werden mit Windows DPAPI geschützt und als `.tmp` abgelegt. Microsoft schließt `.tmp` bei der regulären OneDrive-Synchronisierung aus. [Windows DPAPI](https://learn.microsoft.com/en-us/windows/desktop/api/Dpapi/nf-dpapi-cryptprotectdata), [OneDrive-Dateiregeln](https://support.microsoft.com/en-us/onedrive/restrictions-and-limitations-in-onedrive-and-sharepoint)

Alternativ die CLI direkt verwenden:

```powershell
uv sync --locked --extra desktop
uv run --no-sync computerflow --config config.yaml setup
uv run --no-sync computerflow --config config.yaml server start
uv run --no-sync computerflow --config config.yaml doctor
uv run --no-sync computerflow --config config.yaml listen
```

Zum Testen „Computer, wechsle zum Editor“ in einem Zug sprechen. Alternativ rechte Strg-Taste halten, sprechen und loslassen. „Stopp“ und „Abbrechen“ können während Planung und Sprachausgabe ohne Taste gesagt werden. Ein Textauftrag löst ebenfalls echte Aktionen aus.

```powershell
uv run --no-sync computerflow --config config.yaml command "Setze die Systemlautstärke auf 30 Prozent"
```

Die Konsole zeigt zuerst `Erkannt: …`. Eindeutige Medienformen wie „Pausiere Spotify“, „Spotify, Pause“ und „Spotify, Play“ werden direkt dem richtigen Aktionstyp zugeordnet. Bekannte Programmnamen unterstützen die deutsche Spracherkennung. Unsichere Wörter wie „Chet“ erzeugen eine konkrete Namensrückfrage, keine automatische unscharfe Zielauswahl.

`listen` und `command` starten den verwalteten Server bei Bedarf automatisch; bei fehlender Installation werden die geprüften Dateien eingerichtet. `doctor` allein verändert den Serverzustand nicht, `doctor --offline` kontaktiert ihn nicht. Die Diagnose zeigt Serverbuild, Template-Hash, tatsächliche vom Server gemeldete Quantisierung und die gewählte Laufzeit/GPU. Die Prüfung der Modell-/Projektor-SHA-256 erfolgt beim Einrichten und beim Serverstart. Die automatische Hardwarewahl prüft Vulkan praktisch und verwendet den ersten ausreichend großen gemeldeten Adapter; sie ist kein allgemeiner Leistungsvergleich aller GPUs.

Ein separat selbst verwalteter Server bleibt möglich: `runtime.managed: false`, Endpunkt/Alias konfigurieren und bei Authentifizierung `model.api_key_env` auf eine Umgebungsvariable mit dem Schlüssel setzen. Für diesen Weg verwaltet ComputerFlow keine Laufzeit oder Hardwarewahl.

Ohne `--config` gilt `config.yaml` im Programmordner. Falls sie fehlt, verwendet die CLI Standardwerte. Die [Beispielkonfiguration](config.example.yaml) zeigt die einstellbaren Trigger, `wake.sensitivity`, `wake.silence_seconds`, die Audioantworten (`silent`, `brief`, `conversational`) und `feedback.duck_percent`. ComputerFlow übergibt den Antworttext an die lokale deutsche Windows-Stimme. Der Aktivierungs- und Erfolgston wird separat als Windows-Signalton erzeugt.

Audio und Transkription bleiben im RAM. Im Wake-Modus wertet der lokale Erkenner den laufenden Mikrofonstream aus. Nur ein erfasster Auftrag geht an den lokalen Modellserver. Bei der freiwilligen Stimmprüfung werden drei verschlüsselte Merkmalsvektoren gespeichert. Die Stimmprüfung ist eine zusätzliche Hürde bei Wake-Aufträgen und ersetzt keine Freigabe. Hintergrundgespräche und laute Wiedergabe können die Erkennung stören. Beim Betrieb mit Lautsprechern unterdrückt ComputerFlow neue Wake-Aktivierungen während eigener Ausgaben und lässt die Stopp-Erkennung aktiv.

## Entwicklung und Unterlagen

```powershell
uv sync --locked --extra desktop
uv run --no-sync pytest -m "not windows"
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
```

Die CI führt plattformunabhängige Tests auf Windows, Linux und macOS aus. Dies belegt keine Desktopunterstützung für Linux/macOS. Reale, lesende Windows-Prüfungen sind ausdrücklich aktivierbar:

```powershell
$env:COMPUTERFLOW_WINDOWS_TESTS = "1"
uv run --no-sync pytest -m windows
```

- [AGENT_SPEC.md](AGENT_SPEC.md): Verbindliche Architektur und Ausführungsverträge.
- [PROJEKTENTSCHEIDUNGEN.md](PROJEKTENTSCHEIDUNGEN.md): Beschlossene Projekteigenschaften, Funktionsumfang und spätere Ausbauten.
- [config.example.yaml](config.example.yaml) mit den unterstützten Einstellungen.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): Aktueller Ablauf und Modulgrenzen.
- [docs/VALIDATION.md](docs/VALIDATION.md): Abnahme, Messwerte und verbleibende Grenzen.

`pyproject.toml` und `uv.lock` bestimmen die Installation. `requirements.txt` ist ein bequemer pip-Einstieg, kein eigenständiger Lock. Ein Transformers-Adapter ist noch nicht implementiert.

Wheel und Quellarchiv lassen sich mit `uv build` erzeugen. Beide richten die Modelle separat bei der Installation ein. Ein grafischer Setup-Assistent und der Windows-Installer folgen in späteren Meilensteinen.

## Lizenz

Der Code steht unter [MIT](LICENSE). Die verwendeten Vosk-Modelle stehen laut Modellkatalog unter Apache 2.0. Für die Omni-Gewichte gilt die separate Modelllizenz. [Vosk-Modellkatalog](https://alphacephei.com/vosk/models), [LFM3-Omni-2B GGUF](https://huggingface.co/LiquidAI/LFM3-Omni-2B-GGUF)
