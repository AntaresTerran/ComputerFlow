# Changelog

## 0.0.3 – 5. November 2026

### Nachbesserungen vom 7. November 2026

- Kurze Antworten auf Rückfragen werden im vorgesehenen Aktionstyp geprüft. Neue Aufträge starten mit eigenem Kontext.
- Tab-Aufträge unterstützen gesprochene Varianten wie „Ich wechsle auf den Tab …“ und die Kurzform aus App und beobachtetem Tabtitel.
- Klick- und Stream-Aufträge können zuerst zu einem eindeutigen Fenster oder Tab des genannten Dienstes wechseln. Ein visueller Treffer braucht eine Freigabe.
- Chat-Aufträge erkennen den Zielzusatz auch nach dem Text. Ein führender Abbruch beendet die Aufnahmeverarbeitung. Der Wake-Word-Puffer darf den optionalen Vorlauf kürzen, wenn der Auftrag vollständig enthalten ist.

### Nachbesserungen vom 6. November 2026

- Tab-Aufträge trennen auch bei wechselnder Wortstellung den Tabtitel vom Programmnamen. Für visuelle Ziele grenzt das Modell zuerst die Tab-Leiste ein.
- Chat-Aufträge trennen den Dienstnamen vom Entwurf. Geschrieben wird in ein fokussiertes und über Accessibility bestätigtes Nachrichtenfeld.
- Die Wartezeit für den Beginn des Auftrags startet bei der erkannten Aktivierung, auch wenn das Wake Word mit Verzögerung erkannt wurde.
- Der Schreibpfad unterstützt die Windows-Accessibility-Rolle „Dokument“ und behandelt Wendungen wie „im aktuellen Textfeld“ als Zielbeschreibung.
- Benannte Registerkarten werden anhand ihrer Windows-Accessibility-Rolle und ihres Titels gesucht. Der visuelle Fallback arbeitet mit einem Fensterausschnitt und einer konkreten Klickfreigabe.
- „Öffne …“ kann eine eindeutig im Windows-Anwendungskatalog registrierte App nach Freigabe starten. Folgeaktionen warten auf das nachgewiesene Zielfenster.
- Ein TCP-Reset beim lokalen Modellzugriff wird als Verbindungsfehler gemeldet. Die Windows-CLI nutzt einen Ereignisloop ohne den fehlerhaften Proactor-Abbaupfad.

### Erste Umsetzung

- Windows UI Automation für benannte Elemente sowie Unicode-Eingabe mit Prüfung des aktiven Textfelds.
- Bildkontext bei Bedarf oder zu konfigurierten Aufnahmezeitpunkten. Physische Monitorgrenzen, Ausschnitt, Mausposition und nummerierte Elemente sind an die Aufnahme gebunden.
- Klickvorschau, konkrete Freigabe und begrenzte Aufträge mit mehreren einzeln geprüften Schritten.
- Genaue und relative System-/App-Lautstärke, Browser-Grundbefehle und optionale Sprachfreigabe.
- Deutscher Hörversuch mit der Sprachausgabe des vorhandenen Omni-Modells.

## 0.0.2 – 4. November 2026

- „Computer“ mit vorhandenem deutschem Offline-Vosk-Modell, gemeinsamem Mikrofonpfad, RAM-Ringpuffer, einstellbarer Empfindlichkeit und Sprachende-Erkennung.
- Frei konfigurierbares Tastatur-/Maus-PTT im Halte- und Umschaltmodus. Wake Word und PTT getrennt schaltbar.
- Lokale Aktivierungstöne und deutsche Windows-Sprachausgabe. „Stopp“ und „Abbrechen“ verwenden einen vom Modellserver unabhängigen Audiopfad.
- Freiwillige löschbare Stimmprüfung und optionale vorübergehende Absenkung anderer Wiedergabesitzungen.
- Eindeutige führende Wortbestandteile aus Windows-Produktnamen als Fensterziel, beispielsweise „Steam“.
- Gemeinsamer Programmdatenordner `.computerflow/`; Windows-geschützte Server-Schlüssel und Stimmprofile. Vorhandene Modellgewichte wurden bei der lokalen Migration wiederverwendet.

## 0.0.1 – 3. November 2026

### Nachbesserungen vom 4. November 2026

- Interaktive Mikrofonauswahl, jederzeit über `Start-ComputerFlow.ps1 -Microphone`; Speicherung nach Name/Host-API, WASAPI-Konvertierung für 16 kHz mono und sichtbares aktives Mikrofon.
- Programmnamen/Prozessidentität ergänzen Fenstertitel. Editor und Thunderbird bleiben damit bei geänderter Datei bzw. geändertem Mailordner auffindbar.
- Prompt v3 mit bekannten Programmnamen als ASR-Wortschatzhinweis; sichtbare Transkription in der Konsole.
- Klare Medienbefehle einschließlich „Spotify, Pause“ werden direkt typisiert. Unklare Erkennung löst keine erfundene Fenster-/Wiedergabe-/Lautstärkeaktion aus; „Chet“ kann ChatGPT als Rückfrage vorschlagen.
- Regressionstests für die Rückmeldungen des ersten manuellen Sprachtests.

### Ursprünglicher Stand

Erster lokal abgenommener experimenteller Windows-x64-Stand. Noch kein veröffentlichter Installer.

- Python-Paket, gelockte Abhängigkeiten, CLI und plattformübergreifende Core-CI.
- Eigene Einrichtung von llama.cpp b11960, LFM3-Omni-2B Q4_K_M und Q8_0-Projektor; gepinnte Herkunft, Revisionen, Prüfsummen und separate Modelllizenz.
- Fortsetzbare Downloads, Vulkan-Geräteauswahl, sichtbarer CPU-Fallback sowie authentifizierter Loopback-Server auf Port 47831 mit Start/Status/Stop.
- Push-to-Talk, begrenzte RAM-Aufnahme, deutsche lokale ASR und typisierte Aktionsplanung.
- Lokal gebundene Fenster-/Medienziele, geprüfter Fensterfokus, genaue Systemlautstärke und gezieltes Abspielen/Pausieren.
- Not-Aus, Auftragsdeadline, Rückfragen, Übungsfreigabe, Verwerfen verspäteter Ergebnisse und Unterbrechung bei manuellem Fokuswechsel.
- Regressionen aus echten Modellversuchen: LFM3-Think-Präfix mit JSON-Grammatik, kurzer Sprachabbruch, deutsche Prozentzahlen und vom Modell erfundene Zielpräzisierung.
- Frischstartkorrektur: COM-MTA vor PortAudio initialisieren, damit der erste Mikrofonstart die nachfolgende Audio-/Medienanbindung nicht blockiert; separater Prozessregressionstest.

Abnahme und Grenzen: [docs/VALIDATION.md](docs/VALIDATION.md). Nächster Meilenstein: Wake Word und flüssigere Audiointeraktion in 0.0.2.
