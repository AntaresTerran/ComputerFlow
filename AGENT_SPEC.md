# ComputerFlow – Implementierungsspezifikation

Beschlussstand: 3. November 2026. Verbindliche Zielarchitektur; noch keine implementierte Anwendung. Reihenfolge und Releasekriterien: [ROADMAP.md](ROADMAP.md). Beschlussübersicht: [VERBESSERUNGEN.md](VERBESSERUNGEN.md).

## 1. Leitlinien und Struktur

Windows zuerst; gemeinsame Plattformverträge für späteres Linux/macOS. Lokal, private Nutzung und Open Source, MIT für Code und getrennte Modelllizenzen. Keine hardcodierten Rechner/Pfade/Geräte. PTT zuerst, Wake Word unmittelbar danach. Tests begleiten die Umsetzung; keine separate vorgelagerte Modelltestphase. Jeder Meilenstein liefert einen nutzbaren Durchstich.

Geplante Paketbereiche: core (Konfiguration/Profile/Zustand), audio, vision, brain (Backend-/Modelladapter und Aktionsschema), actuator (Richtlinien/Ausführung/Prüfung), platform, integrations sowie panel (Server/Web/Tray/Setup). Tests liegen unter tests.

Plattformadapter kapseln Fenster, UI-Elemente/semantische Aktionen, Unicode-Text, Tastatur/Maus, Capture/DPI, Medien/Lautstärke und Berechtigungen. Nicht verfügbare Fähigkeiten sichtbar melden. Mock-Tests belegen keine reale Plattformunterstützung.

## 2. Audio und Trigger

- Ein gemeinsamer Aufnahmeweg versorgt Ringbuffer, Wake Word und Auftragsaufnahme. Inferenz darf Audio und Not-Aus nicht blockieren.
- PTT: rechte Strg-Taste halten; Loslassen startet Verarbeitung. Umschaltmodus sowie freie Tastatur-/Maustasten sind Alternativen.
- Wake-Word-Adapter mit austauschbarer Modellquelle: zunächst vorhandenes „Computer“-Modell prüfen und verwenden. Kein mitgeliefertes openWakeWord-Standardmodell unterstellen.
- Modellherkunft, Lizenz, Revision und Prüfsumme erfassen. Nutzermodelle und persönliche Stimmen außerhalb des Repos. Optionaler Verifier standardmäßig aus; keine Sicherheitsauthentifizierung.
- 16 kHz mono und zwei Sekunden Ringbuffer sind Ausgangswerte; Wake-Word-Schnitt/Pre-Roll müssen Satzanfänge erhalten.
- Sprachende-Erkennung und Empfindlichkeit einstellbar, 1,2 Sekunden Stille vorläufiger Ausgangswert. Maximale Aufnahmedauer begrenzen.
- Wake Word und PTT einzeln/gemeinsam nutzbar. Eigene Töne bei Audioverarbeitung berücksichtigen; eigene Sprachausgabe bleibt unterbrechbar.
- Musik-/Stream-/Lautsprecherbedingungen praktisch prüfen, Echounterdrückung vorsehen. Optionales Absenken der Wiedergabe einschließlich Wiederherstellung bei Fehler/Abbruch.

## 3. Kontext und Grounding

Reihenfolge: direkte Schnittstelle → Accessibility → visuelle Bedienung. Wenn möglich UI-Elemente semantisch aktivieren oder Werte setzen.

- Standard: Bildschirmkontext nach Bedarf. Fehlende Bilder selbstständig nachfordern; manuelle Capture-Optionen on_wake, on_speech_end und both bleiben möglich.
- Bezug: angesprochenes/aktives Fenster, für Zeigebezüge zusätzlich zeitlich zugehörige Mausposition. Mehrdeutigkeit durch Rückfrage auflösen; fester Monitor manuell wählbar.
- SnapshotContext enthält eindeutige ID, monotone Aufnahmezeit, Fenster-/Monitor-ID, physische Monitorgrenzen, Originalgröße, Ausschnitt, Skalierung/gegebenenfalls Padding sowie Cursorposition und deren Zeitbezug.
- Aktionen referenzieren den konkreten Aufnahme-/Elementkontext. Bei zwei Bildern, Monitorwechseln oder Crops muss die Zuordnung eindeutig sein.
- Interne Normalisierung 0..1000 möglich; modellnative Formate im Adapter übersetzen. Endpunkte, Crops, Padding, negative Monitorpositionen und gemischte Skalierungen korrekt rückrechnen und testen.
- Windows-DPI-Awareness möglichst Per-Monitor v2 vor GUI-Initialisierung. PyAutoGUI allein ist keine Grundlage für garantierten Mehrmonitorbetrieb oder Unicode; geeignete Plattformimplementierungen vorsehen.
- SoM nutzt kontextgebundene Elementkennungen, Labels und Grenzen; nummerierte Bildmarkierungen bei Bedarf. Sichtbarkeit auf Wunsch im Übungs-/Debug-Modus.
- Kurze Zielvorschau vor visuellen Klicks standardmäßig an, Dauer einstellbar und abschaltbar. Eigene Overlays aus Analysebildern ausblenden.

## 4. Inferenz und Aktionsvertrag

- Erster Weg: lokaler llama.cpp-Server und LFM3-Omni-2B-GGUF. Austauschbare Backend-/Modelladapter; Transformers möglicher alternativer Weg.
- Backend, Beschleunigung und Quantisierung getrennt konfigurieren. Unterstützte Kombinationen beim Einrichten praktisch prüfen, automatisch wählen und gerätespezifisch speichern. Manuelle Kontrolle und sichtbarer CPU-Fallback.
- Tatsächlich aktive Hardware/Laufzeit anzeigen; keine pauschale CUDA/DirectML/NPU-Unterstützung behaupten.
- Modellrevision, Laufzeit-, Prozessor-/Template- und Promptversion nachvollziehbar halten; Abhängigkeiten reproduzierbar festlegen.
- Modellspezifisches offizielles Chat-/Tool-Template verwenden, Aktionsplanung explizit als Text-/Tool-Ausgabe. Native Tool-Ausgaben im Adapter normalisieren. Grammar/Constrained Decoding einsetzen, soweit mit dem Backend kompatibel; Validierung bleibt erforderlich.
- Typisierte diskriminierte Aktionen mit begrenzten Parametern, Ziel- und Kontextreferenzen. Unbekannte Aktionen, unerlaubte Zusatzfelder, ungültige Koordinaten und unvollständige Antworten zurückweisen; begrenzte Korrekturanfrage erlauben.
- Modell-/Verbindungsfehler unterbrechen kontrolliert. Mock-Modus nur ausdrücklich zur Entwicklung und getrennt von realer Ausführung; kein automatischer Mock-Fallback.

Aktionsfamilien: Fensterfokus, UI-Element bedienen, begrenzte Maus/Scroll/Hotkey-Aktionen, Unicode-Text, Medien und genaue Lautstärke, HTTP(S)-URL öffnen, registrierte App starten, optionale Tab-Aktionen, Kontextnachforderung und Rückfrage. Plugins ergänzen validierte Aktionen. Keine Shell-Aktion.

## 5. Ausführung und Sicherheit

Je Auftrag: eindeutige ID, Abbruchkennung, Deadline und Ausführungsstand. Zustände: Aufnahme, Planung/Kontextbeschaffung, Rückfrage/Bestätigung, Ausführung, Prüfung und Abschluss/Fehler/Abbruch.

Ablauf: normalisieren/validieren → Ziel/Fokus/Kontext prüfen → Richtlinie/Freigabe prüfen → einen Schritt ausführen → Ergebnis prüfen → Kontext aktualisieren und fortsetzen, begrenzt neu planen oder nachfragen.

- Alltagsbedienung direkt. Senden, Kaufen, Löschen, Verwerfen ungespeicherter Änderungen und sensible Einstellungsänderungen vor dem verbindlichen Schritt bestätigen.
- Bestätigung an Aktion, Ziel und Inhalt binden, zeitlich begrenzen und bei Änderungen verwerfen. Sprache („Computer, bestätigen“/„Abbrechen“) und Panel unterstützen. Executor entscheidet unabhängig vom Modell; Schlüsselwörter allein genügen nicht.
- Shell-Verbot auch für Hotkey-/Text-/App-Kombinationen durchsetzen. Programmstarts nur über registrierte Anwendungen/Aliase mit geprüften Parametern. URLs nur HTTP(S).
- Bildschirm-/Plugininhalte als untrusted Daten behandeln; sie dürfen keine Berechtigungen oder Freigaben erteilen.
- Nach relevanten UI-Änderungen erneut prüfen. Klick → Texteingabe erfordert richtigen Eingabefokus. Gesendetes OS-Ereignis allein ist kein Erfolg.
- Keine blinden Wiederholungen nicht idempotenter Aktionen wie Wiedergabe umschalten oder Nachricht senden.
- Globaler konfigurierbarer Not-Aus und Sprachstopp unabhängig von Inferenz. Abgebrochene Aufträge durch verspätete Antworten niemals fortsetzen. Tasten und vorübergehende Audioänderungen sicher zurücksetzen.
- Relevante manuelle Fenster-/Fokusänderung unterbricht UI-Aktion und löst Zustandsprüfung aus. Wiederherstellung zeitlich und in Versuchen begrenzen, ausgeführte Teilschritte ausweisen; keine pauschale Rückgängigmachung versprechen.
- Übungsmodus zeigt nächsten Schritt/Ziel und Bedienweg, führt erst nach ausdrücklicher Freigabe aus.

## 6. Browser und Plugins

- Browserübergreifende Grundbedienung ohne Erweiterung erhalten und praktisch erproben. Nicht jede Drittanwendung ist automatisch als kompatibel anzusehen.
- Erste optionale Erweiterung für Firefox. Chrome/Edge und weitere später.
- Browser-/Profil-/Tabkontext, Verbindungsstatus und Fähigkeiten melden. Bei Mehrdeutigkeit nachfragen; ohne Erweiterung auf allgemeine Bedienwege zurückgreifen.
- Lokale Verbindung authentifizieren und Gegenstellen prüfen.
- Plugins einzeln aktivieren, Aktionen und Zugriffe beschreiben. Nur verfügbare aktive Tools dem Modell anbieten. Richtlinien, Abbruch und Ergebnisprüfung gelten auch hier.
- Eigene Integrationen nutzen den Pluginvertrag; komfortable Community-Installation später.

## 7. Oberfläche und Funktionen

- Lokales Web-Panel plus Tray für Pause, Trigger, Status, Einstellungen, Verlauf, Profile, Plugins und Makros. Zu Beginn genügt eine minimale Oberfläche für den jeweiligen Meilenstein.
- Setup: Mikrofon/Pegel, PTT, Modelle/Laufzeit mit Downloadfortschritt und lokalen Alternativen, Hardwarewahl, Berechtigungen, Probebefehl; Wake-Word-Kalibrierung/Verifier nach Verfügbarkeit.
- Loopback-Bindung, zufälliges Sitzungstoken, Host-/Origin-Prüfung, CSRF-Schutz und restriktive CORS-/WebSocket-Regeln. Token nicht in URLs/Logs. Fehlende Komponenten/Berechtigungen mit Lösungsschritten anzeigen.
- Lokale Sprachausgabe standardmäßig knapp, still/gesprächig wählbar. Rückfragen/Freigaben/Fehler sprechen, einfache Erfolge per Ton; Inhalte im Panel verfügbar halten.
- Kurzzeitgedächtnis standardmäßig an, zeitlich/inhaltlich begrenzt, RAM. Ziele erneut prüfen. „Vergiss den Kontext“ löscht es; keine impliziten dauerhaften Erinnerungen.
- Diktieren explizit starten/pausieren/beenden; gewöhnliche Sprache als Text, klar reservierte Steuerbefehle. Satzzeichen/Umlaute/Unicode, Pause bei unerwartetem Eingabezielwechsel. Absenden eigener bestätigungspflichtiger Schritt.
- Vorlesen/Zusammenfassen/Erklären bezieht sich auf Auswahl, aktives Fenster oder Cursorbereich. Text-/Accessibility-Quellen bevorzugen, Bilder nach Bedarf; Ausschlüsse beachten.
- Medien: relative/genaue Lautstärke, System und einzelne Anwendungen unterscheiden. Explizites Wiedergabeziel, sonst letzter eindeutiger Bezug/eindeutig aktive Wiedergabe; Mehrdeutigkeit klären.
- Anwendungen erkennen, Aliase je Gerät im Panel zuweisen.
- Makros/Szenen mit Bearbeitung/Import/Export und Gerätebindung. Sprachbeschreibungen ergeben geprüfte Entwürfe; dieselben Ausführungsregeln verwenden.

## 8. Datenschutz und Profile

- Audio/Bilder standardmäßig RAM, nach Abschluss bzw. Ende des notwendigen Verwendungszwecks freigeben. Sitzungsverlauf mit Auftrag/Aktionen/Ergebnis.
- Dauerhafte Historie/Debug-Daten nur ausdrücklich aktivieren; Zeit-/Speichergrenzen und Löschfunktion. Logs dürfen dies nicht umgehen.
- Aufnahme-Ausschlüsse vor Capture prüfen, auch sensible Fenster in größeren Bildausschnitten berücksichtigen. Bei benötigtem ausgeschlossenen Bildkontext Einschränkung erklären und erlaubte Alternativen prüfen.
- Korrekturen freiwillig als lokale Testfälle. Audio/Bilder separat ausdrücklich freigeben. Alias-/Makro-Vorschläge vor Übernahme bestätigen. Automatisches Modelltraining später optional.
- Benutzerspezifische Verzeichnisse, wählbarer Modellpfad, Standardprofil und weitere Geräteprofile. Import prüft Geräte/Pfade; Stimmen und Geheimnisse nicht stillschweigend exportieren.

## 9. Paketierung und begleitende Qualität

Bei Implementierung pyproject.toml, uv-Lockfile und passende optionale Extras erstellen. Requirements sind derzeit vorläufig.

Automatisierte Prüfungen für Konfiguration, Transformationen, Aktionsvertrag, Bestätigungsbindung, Abbruch und verspätete Ergebnisse. Modellversuche prüfen Format und tatsächlichen Auftragserfolg samt Latenz/Speicher. Fehler als Regressionen aufnehmen; simulierte und echte Bedienung getrennt ausweisen.

GitHub Actions für plattformunabhängige Tests auf Windows/Linux/macOS; reale Plattformadapter auf ihrem Zielsystem prüfen, sobald umgesetzt. Windows-Installer geplant, portable Ausgabe später optional. Releaseumfang folgt ROADMAP.md.
