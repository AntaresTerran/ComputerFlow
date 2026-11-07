# Lokale Abnahme

## Praxistest-Rückmeldung vom 7. November 2026

- 200 automatisierte Tests einschließlich Windows-Integration bestanden. Ruff meldete keine Abweichungen.
- Drei Formulierungen aus dem Nutzerprotokoll führten mit lesenden Windows-Daten zur Auswahl des tatsächlich geöffneten Tabs „Home Assistant“. Die Tab-Auswahl wurde geplant. Zwei unverständliche Transkriptionen führten beim lokalen Modell zu einer neuen Bitte um Wiederholung.
- Klick, Stream und Chat behalten ihren Aktionstyp und den genannten Dienst. Tests prüfen die Reihenfolge aus Tab-Auswahl und Zielsuche auf einer simulierten Oberfläche. Das Modell übernimmt den erkannten Nachrichtentext als Entwurf. Der echte Twitch-Chat und der Wechsel auf einen konkreten Live-Stream bleiben Teil der praktischen Erprobung.
- Ein führendes „Abrechen.“ stoppt den Auftrag auch bei weiterem transkribierten Text. Ein Audiopuffer-Test prüft, dass nur der optionale Vorlauf gekürzt werden kann.

## Tab- und Chat-Rückmeldung vom 6. November 2026

- 188 automatisierte Tests einschließlich Windows-Integration bestanden. Ruff meldete keine Abweichungen.
- Die Transkriptionen „Wechsel auf den Home Assistant Tab von Firefox“ und „Wechsle den Firefox-Tab auf Olamä“ ergeben getrennte Tab- und App-Namen. Weitere Wortstellungen werden mit einem Tab-Schema am lokalen Modell geprüft.
- Auf dem angehängten Bild schlug die ursprüngliche Bildsuche das Lesezeichen „Home Assistant“ vor. Mit getrennt erkannter Tab-Leiste lagen die vorgeschlagenen Punkte auf „Home Assistant“ und „Claude Code - Ollama“. Die Grafik wurde für die Prüfung im RAM verarbeitet. Die Klicks wurden am Bild geprüft.
- Die Chat-Prüfung verwendet ein simuliertes Nachrichtenfeld neben einem Suchfeld. In einem falschen Fenster oder mit Fokus im Suchfeld bittet ComputerFlow um den richtigen Fokus. Im bestätigten Chatfeld wird nur der diktierte Text als Entwurf gebunden. Der Live-Chat war kein Ausführungsziel.

## Nachbesserungen an 0.0.3 am 6. November 2026

- 178 automatisierte Tests einschließlich Windows-Integration bestanden. Ruff meldete keine Abweichungen.
- Die deutsche Wake-Word-Prüfung verarbeitet einen direkt anschließenden Satz sowie einen Auftrag nach einer bewusst eingelegten Pause. Das alleinstehende Wake Word endet ohne Aktion.
- Der moderne Windows-Editor meldete sein Textfeld als UI-Automation-Dokument (50030) mit schreibbarem Value-Pattern. Diese Standardrolle wird unabhängig vom Programm erkannt. Die automatisierten Tests prüfen wörtliche Eingabe, eindeutige Fokussierung und die Sperre bei einem geschützten oder unvollständigen Kontext. Der Schreibtest im echten Editor blieb offen, weil die Computer-Use-Freigabe zum Aktivieren des leeren Testfensters ablief.
- Der tatsächlich offene Firefox-Tab „Home Assistant“ wurde lesend über seine Windows-Accessibility-Rolle aufgelöst. Das echte lokale Bildmodell fand dieselbe Beschriftung in einer Testgrafik mit drei Registerkarten. Ein automatisierter Test prüft den visuellen Pfad und die Klickfreigabe mit einem beliebigen Testprogramm. Ein weiterer findet eine Stream-Registerkarte in einem Programm, dessen Prozessname und Fenstertitel keinen Hinweis auf den Dienst geben.
- Windows registriert „Editor“ in seinem lokalen Anwendungskatalog. Der Ausführungstest bindet einen beliebigen Katalognamen und eine geprüfte Registrierung an den freigabepflichtigen App-Start.
- Ein absichtlich zurückgesetzter TCP-Loopback-Socket führte zu einer sichtbaren Meldung über den lokalen Modellserver und zu keinem Traceback beim Verbindungsabbau.

## Version 0.0.3 am 5. November 2026

- 169 automatisierte Tests bestanden, einschließlich Windows-Integration. Die neuen Fälle prüfen unter anderem negative Monitorkoordinaten, eine an den Bildkontext gebundene Freigabe, eindeutige App-Lautstärke und den Abbruch einer Schrittkette bei unerwartetem Vordergrund.
- `scripts/validate_ui.py` benutzt ein eigenes WinForms-Testfenster. Es prüft den Aufnahmeschutz, Unicode-Eingabe einschließlich `Grüße, 世界 und 🐈.`, eine Accessibility-Checkbox und eine Schaltfläche. Die stumme Wiedergabesitzung des Testprogramms wurde auf 23 % gesetzt, zurückgelesen und danach wiederhergestellt.
- Das echte lokale LFM3-Omni-Bildmodell fand eine beschriftete Fläche ohne aktivierbares Accessibility-Element. Der Klick erfolgte über Vorschau und gebundene Freigabe. Die Farbänderung wurde am Ziel gemessen. „Klick hier“ wurde auf drei physischen Monitoren geprüft, darunter ein Monitor links von x = 0. Windows meldete Skalierungen von 100 % und 150 %.
- Ein zweistufiger Auftrag stellte ein minimiertes eigenes Fenster wieder her, erfasste dessen Vordergrund neu und schrieb erst dann in sein aktives Textfeld. Das Testfenster erteilte der Prüfsoftware gezielt die Windows-Fokusberechtigung. Im normalen Einsatz entscheidet Windows weiterhin über Fokuswechsel.
- In einem separaten Chrome-Profil an einer lokalen Seite funktionierten Adressleistenfokus und geprüfte Texteingabe als Schrittkette ohne Erweiterung. Der Einrichtungsdialog eines frischen Firefox-Testprofils verhinderte einen Nachweis derselben Kette in Firefox. Der Assistent stoppte vor der Eingabe.
- Vosk erkannte „Computer bestätigen“ in einem synthetischen Sprachtest nach 1,95 s ab Beginn der Datei. Sprachfreigabe ist eine ausdrücklich aktivierbare Option.

Der optionale Hörversuch mit dem vorhandenen LFM3-Omni-2B-GGUF und `llama-tts` erzeugte 4,48 s deutsche Sprache bei 24 kHz. Der kalte Einzelaufruf dauerte rund 9,4 s, davon 3,05 s für Prompt und Generierung nach der Initialisierung. Das separate deutsche Vosk-Modell transkribierte alle Wörter der Hörprobe. Latenz im durchgehend laufenden Assistenten und Sprachqualität über unterschiedliche Sätze wurden damit noch nicht gemessen. [Modellkarte](https://huggingface.co/LiquidAI/LFM3-Omni-2B-GGUF)

Für die native UI-Prüfung aus dem Programmordner `.\.computerflow\venv\Scripts\python.exe -X utf8 .\scripts\validate_ui.py` ausführen. Das Skript kompiliert eine eigene WinForms-Testoberfläche und bedient deren zwei Fenster.

## Version 0.0.2 am 4. November 2026

- Der lokale Windows-Starter meldete 0.0.2, Logitech StreamCam über WASAPI und den authentifizierten Modellserver auf `127.0.0.1:47831` mit Vulkan auf der Radeon RX 7900 XTX. Die StreamCam lieferte native 16-kHz-Monoblöcke. Mikrofonproben wurden nach dem Test verworfen.
- Die bestehenden GGUF-Dateien und Laufzeitarchive wurden mit SHA-256 in den Projektordner übernommen. Nach dem Start der neuen Installation wurden die 113 Dateien der alten AppData-Installation mit ihren Kopien beziehungsweise neu erstellten Laufzeitmetadaten abgeglichen und die alte Installation entfernt.
- `scripts/validate_voice.py` verwendet Vosk, die produktive Aufnahmesitzung und den echten llama.cpp-Modellserver. „Computer wechsle zum Editor“ ohne Pause ergab den richtigen Fenstertyp. Der Lautstärkebefehl ergab mit beigemischter Musik den exakten Sollwert 50 %. Mit leiser überlagerter Sprachspur blieb der Fensterauftrag erkennbar. Ein alleinstehendes „Computer“ führte zu keinem Auftrag. Die Ergebnisse dieser Prüfungen wurden vor Systemaktionen abgefangen.
- Synthetische Stopp-Befehle wurden nach 0,90 s für „Stopp“, 1,15 s für „Abbrechen“ und 2,20 s für „Computer, Stopp“ erkannt, jeweils ab Beginn der Testdatei. Mit demselben Audiopfad wurden eine blockierte Planung und die tatsächlich laufende lokale SAPI-Ausgabe unterbrochen. Ein Sprachbefehl aus einem realen Raum kann aufgrund von Lautsprecherpegel und Mikrofonabstand anders ausfallen.
- Die Tests für Fensterauswahl decken „Steam“ bei Windows-Produktname „Steam Client WebHelper“ und einen zweiten beliebigen Produktnamen ab. Mehrere Fenster desselben Produkts führen zu einer Rückfrage.
- Der optionale Verifier akzeptierte in einem RAM-Test einen neuen Satz derselben synthetischen Stimme und wies eine andere synthetische Stimme zurück. Die Stimmprüfung ist standardmäßig aus.
- 163 automatisierte Tests bestanden, einschließlich der aktivierten Windows-Integration.

Im anschließenden Praxistest reagierte „Computer“ auch bei moderaten Hintergrundgeräuschen und Musik. Bei lauter Musik wurde die Aktivierung weniger zuverlässig. Fensterwechsel und Mediensteuerung funktionierten in den meisten Fällen. Windows verweigerte einzelne Fokuswechsel.

Wiederholung aus dem Programmordner nach `Start-ComputerFlow.ps1 -Doctor`:

```powershell
.\scripts\create_validation_audio.ps1
.\.computerflow\venv\Scripts\python.exe .\scripts\validate_voice.py
```

## Version 0.0.1

Stand: 4. November 2026; Basisabnahme vom 3. November 2026. **Experimenteller Windows-x64-Entwicklungsstand lokal abgenommen.** Noch kein öffentlicher Release und kein Installer veröffentlicht.

## Eingerichtete Kombination

| Bestandteil | Geprüfter Stand |
|---|---|
| Laufzeit | llama.cpp b11960 / Commit `8642541b255bfb5dc39cd351a178be09013a55d6` |
| Modell | LiquidAI/LFM3-Omni-2B-GGUF, Q4_K_M |
| Modellrevision | `d508b88f08a5b4286f2d2805a6a8d69a0ff44c72` |
| Projektor | mmproj-LFM3-Omni-2B-Q8_0.gguf |
| Template-SHA-256 | `4e295a038af980438912483abe76a81c36b2451c87ccc1e62051529a6a0fb7f5` |
| Prompt | Basisabnahme v2; aktueller Client v4 mit den oben beschriebenen Tab-Nachbesserungen |
| GPU | Vulkan / AMD Radeon RX 7900 XTX; CPU-Betrieb ebenfalls real geprüft |
| Python | 3.13.13, Installation aus `uv.lock` |
| Modellserver | `127.0.0.1:47831`, API-Schlüssel, keine Agenttools/Web-UI/Protokollierung |

Die festgelegten SHA-256-Prüfsummen für Binärarchive, Modell, Projektor, Modellkarte und separate Lizenz stehen in [runtime/artifacts.py](../src/computerflow/runtime/artifacts.py). Alle Downloads wurden geprüft. Herkunft: [offizieller llama.cpp-Build](https://github.com/ggml-org/llama.cpp/releases/tag/b11960) und [offizielle Modellquelle](https://huggingface.co/LiquidAI/LFM3-Omni-2B-GGUF).

8080 war nicht belegt; der Modellserver fehlte vollständig. Der projektspezifische Standardport 47831 wurde auf Wunsch festgelegt und ist jetzt tatsächlich gebunden. Die fehlende Erreichbarkeit war kein nachgewiesener Firewallfehler. Reale lokale Anfragen funktionieren mit der eingerichteten Konfiguration.

## Automatisierte Regressionen

156 bestandene pytest-Tests, davon vier ausdrücklich aktivierte reale Windows-Prüfungen. Neben drei lesenden Plattformprüfungen startet ein isolierter Prozess zuerst das Mikrofon und prüft danach den ersten Desktop-/Audio-Snapshot; Mikrofonblöcke werden dabei verworfen. Die übrigen Prüfungen decken Konfiguration, strikte Modell-/Aktionsschemata, unbekannte/doppelte Felder, sichere YAML-Verarbeitung, Loopback, Download-Fortsetzung und SHA-256, ZIP-Pfade, Prozessbesitz, Startsperre, sichtbaren CPU-Fallback, PTT, Aufnahmegrenzen, Deadline, Abbruch, Freigaben und eindeutiges Grounding ab. Ruff und Paketbau werden zusätzlich geprüft.

Fehler aus echten Modellversuchen wurden als Regressionen aufgenommen:

- Der rohe Reasoning-Modus kollidierte mit LFM3s leerem Think-Steuerblock und der JSON-Grammatik. Der automatische Parser ist mit dem echten Build geprüft.
- Direkte Audioplanung deutete einen kurzen Abbruch falsch. Die offizielle ASR-Aufgabe erkennt ihn; ein reservierter kurzer Stopp beendet lokal vor der Planung.
- Eine deutsche ASR-Probe zerlegte „neununddreißig“ in „9 und 30“. Eine eng begrenzte Prozentkorrektur wird geprüft.
- Das Modell ergänzte bei mehrdeutigen Fenstern einen nicht genannten Namenszusatz. Zielnamen werden jetzt lokal zugeordnet; erfundene Zusätze oder mehrere Treffer führen zur Rückfrage.
- In einem frischen CLI-Prozess initialisierte PortAudio vor dem ersten Snapshot den falschen COM-Threadmodus. Die Windows-Plattform initialisiert COM jetzt vor dem Mikrofonstart im benötigten MTA-Modus. Der isolierte Frischstart-Test belegt danach funktionierendes Core Audio und SMTC. Firefox-Kanalpegel blieben bei dieser Prüfung unverändert auf 100 Prozent.

## Echte Abnahme

Das wiederholbare Skript [scripts/validate_release.py](../scripts/validate_release.py) bestand 13 Fälle mit laufendem Modellserver und realen Windows-Adaptern:

1. Synthetischer deutscher Sprachauftrag durch den begrenzten PTT-Verarbeitungsweg setzt Systemlautstärke auf 39 Prozent und liest sie zurück.
2. Sprachauftrag fokussiert das eigene Testfenster Alpha und prüft den tatsächlichen Vordergrund.
3. Zwei passende Testfenster erzwingen eine Rückfrage ohne Aktion.
4. Die eindeutige Antwort auf die Rückfrage fokussiert Beta mit frischem Kontext.
5. Sprachauftrag pausiert den eigenen stummen Windows-Testplayer, Playback-Status wird geprüft.
6. Sprachauftrag startet denselben Player, Playback-Status wird geprüft.
7. Gesprochenes „Abbrechen“ beendet den Auftrag ohne Aktion.
8. Eine reale geplante Aktion wartet auf ihre konkrete Übungsfreigabe.
9. Abbruch während einer echten Modellanfrage verwirft das Ergebnis.
10. Manueller Fensterwechsel während einer echten Planung verhindert die Aktion.
11. Das echte Mikrofon wird kurz geöffnet und PCM16-Aufnahme ausschließlich im RAM geprüft und verworfen.
12. Der echte globale Tastaturhook lässt sich öffnen und sauber schließen.
13. Ein Metadatenzugriff ohne API-Schlüssel wird mit HTTP 401 zurückgewiesen.

Das Skript verwendet eigene Testfenster und einen eigenen stummen Player. Fremde Wiedergabe wird nicht gesteuert; ursprüngliche Systemlautstärke und Vordergrund werden abschließend wiederhergestellt.

Zusätzlich real geprüft: Server stoppen, kontrollierter Verbindungsfehler ohne Aktion, anschließender Neustart, Start und sauberes Schließen des echten PTT-Aufnahmebetriebs. Der CPU-Server wurde separat gestartet und erkannte denselben gesprochenen Prozentauftrag zu einer gültigen 39-Prozent-Aktion; danach wurde Vulkan wiederhergestellt.

Die gemessenen synthetischen Sprachaufträge lagen nach Bereitstellung des Audioblocks bei rund **0,27–0,44 Sekunden** für Inferenz plus Aktion/Prüfung. Das ist keine Messung menschlicher Sprechdauer oder kalter Modellstarts. Der Modellserver belegte dabei rund **1,5 GiB Prozess-RAM**. Windows-GPU-Prozesszähler wiesen nach dem Vulkan-Neustart rund **2,6 GiB dedizierten Grafikspeicher** für den Server aus; gemeldete Setup-Speicherwerte sind davon getrennt.

## Praktische Grenzen

Die Abnahme nutzt lokal synthetisierte deutsche Sprachdateien, die in den echten Recorder-/PTT-Verarbeitungsweg eingespeist werden. Physischer Tastendruck mit gleichzeitig selbst gesprochenem Auftrag, individuelle Stimme, Raumakustik, Lautsprecher-Echo und Musikbedingungen wurden damit nicht als bestanden erklärt. Echte Mikrofonaufnahme und Hook-Verfügbarkeit wurden separat geprüft. Diese Alltagserprobung sowie Wake Word, Sprachstopp während laufender Inferenz und Audioausgabe gehören zum anschließenden Ausbau.

Nur diese Windows-x64-Konfiguration ist real geprüft. Core-CI auf Linux/macOS belegt keine Desktopunterstützung. Der aktuelle Stand führt eine erlaubte Aktion je Auftrag aus und unterstützt keine generische UI-Eingabe, Screenshots, Browsererweiterung, Shell, Senden/Kaufen/Löschen oder grafische Einrichtung.

Bei einer Wiederholung aus einem Hintergrundprozess verweigerte Windows den Fokuswechsel. Der Adapter meldete das nicht bestätigte Ergebnis korrekt als Fehler. Windows garantiert `SetForegroundWindow` nicht aus jedem Vordergrund-/Eingabezustand; ComputerFlow ändert dafür keine globale Fokusrichtlinie. Der vollständige 13-Fälle-Durchlauf war zuvor erfolgreich. Für reproduzierbare interaktive Prüfungen kann das Testfenster über den Startknopf aktiviert werden. Eine zusätzliche Aktivierung über Computer Use wurde mangels erteilter App-Freigabe nicht ausgeführt; sie ist kein weiterer bestandener Test.

## Wiederholung

```powershell
uv sync --locked --extra desktop
uv run --no-sync pytest -m "not windows"
$env:COMPUTERFLOW_WINDOWS_TESTS = "1"
uv run --no-sync pytest -m windows
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv build
uv run --no-sync computerflow --config config.yaml doctor
```

Die folgenden ausdrücklich gewählten Abnahmeskripte erzeugen synthetische Testdateien unter `.computerflow/validation`, öffnen eigene Testfenster und einen stummen Player und ändern vorübergehend die Systemlautstärke.

```powershell
.\scripts\create_validation_audio.ps1
uv run --no-sync python scripts/validate_release.py config.yaml --interactive
```

Im Testfenster Beta auf **Abnahme starten** klicken und während des Durchlaufs den Fokus nicht selbst ändern. Ohne `--interactive` läuft das Skript sofort; Windows kann dann bei Aufruf aus dem Hintergrund den Fokuswechsel verweigern.

Die Dateien sind keine persönlichen Sprachaufnahmen. Reale Windows-/Asyncio-Prüfungen benötigen eine normale interaktive Sitzung; unter einer eingeschränkten Windows-Sandbox können COM-/WinRT-Aktivierung oder die Ereignisschleife blockieren.

## Rückmeldungen des manuellen Tests vom 4. November 2026

Gemeldet wurden die fehlende sichtbare Mikrofonauswahl, wechselnde Dokument-/Ordnernamen statt Programmnamen sowie die Erkennung „Chet“/„Hausier Spotify“. Diese Fälle sind jetzt Regressionen.

- Logitech StreamCam über WASAPI eindeutig ausgewählt und in der lokalen Projektkonfiguration gespeichert. Eine kurze 16-kHz-mono-Aufnahme im RAM funktionierte. Windows-Standardmikrofon und Firefox-Kanalpegel blieben unverändert; die Prüfdaten wurden verworfen.
- Mikrofonwahl mit umsortierten PortAudio-IDs, fehlendem Gerät, doppelten Namen, explizitem Windows-Standard und ungültiger Auswahl automatisiert geprüft.
- Namensauflösung für Editor mit reinem Dateititel sowie Thunderbird mit Posteingang/Gesendet/Entwürfe automatisiert geprüft. Reale ChatGPT-/Thunderbird-/Spotify-Prozessmetadaten wurden lesend ermittelt; reine Live-Planungen adressierten die passenden vorhandenen Fenster/Sitzungen.
- Fünf lokal synthetisierte deutsche Sprachaufträge am echten Modell geprüft: ChatGPT, Thunderbird, Editor, „Pausiere Spotify“ und „Spotify, Pause“. Der Editor-Kontext war hierfür ein explizites Dateititel-Testfixture; die übrigen Programme/Sitzungen kamen aus dem realen Desktopkontext. Es wurden dabei keine fremden Fenster aktiviert und keine fremde Wiedergabe verändert.
- „Wechsle zu Chet“ erzeugt eine konkrete ChatGPT-Rückfrage. „Hausier Spotify“ erzeugt eine Medienrückfrage statt einer geratenen Fokus-/Play-/Lautstärkeaktion. Mehrere Fenster desselben Programms bleiben mehrdeutig.

Die aktualisierten 156 pytest-Tests bestehen. Die Sprachproben verwenden synthetische Sprache; die individuelle Stimme des Nutzers muss mit der gewählten Webcam erneut praktisch erprobt werden. Die frühere Basisabnahme mit echten Systemaktionen und die unveränderten Windows-Fokusbeschränkungen bleiben getrennt davon dokumentiert.
