# ComputerFlow – Projektentscheidungen und Funktionsumfang

Stand **4. November 2026**. „Geplant“ kennzeichnet beschlossene, spätere Funktionen. Reihenfolge und technische Verträge stehen in [ROADMAP.md](ROADMAP.md) und [AGENT_SPEC.md](AGENT_SPEC.md).

## 1. Rahmen und Vorgehen

- Lokal, primär privat und Open Source. MIT für Code; Modelle mit eigener Lizenz/Herkunft behandeln.
- Universelles Ziel über unterschiedliche Hardware hinweg. Windows zuerst, gemeinsame Plattformverträge für Linux/macOS.
- Umsetzung mit begleitenden Tests. Die ursprünglich vorgeschlagene separate Phase 0.5/Modelltestphase entfällt.
- PTT zuerst und Wake Word unmittelbar danach. Bedarfsgesteuerte Verarbeitung muss nötigen Kontext selbst nachholen; fehlende Fähigkeiten sichtbar melden.
- Erste Version 0.0.1, größere nutzbare Etappen, langer offener Weg bis 1.0.
- Alle ComputerFlow-eigenen Dateien und Daten bleiben in passenden Unterordnern des Programmordners. Das gilt rückwirkend und für Entwicklung und Release. Dazu gehören Modelle, Laufzeit, Profile, Caches und temporäre Dateien.

## 2. Audio und Rückmeldung

| Punkt | Beschluss |
|---|---|
| Wake-Word-Quelle | Austauschbar; zunächst vorhandenes „Computer“-Modell, eigene Modelle später möglich. Kein angeblich mitgeliefertes openWakeWord-Modell voraussetzen. |
| Persönliche Stimme | Verifier freiwillig, standardmäßig aus; lokal und löschbar; ersetzt keine Aktionsbestätigung. |
| PTT | Rechte Strg-Taste halten; Loslassen verarbeitet. Freie Tastatur-/Maustasten und optionaler Umschaltmodus. |
| Betriebsarten | PTT und Wake Word einzeln/gemeinsam. |
| Aufnahme | Ringbuffer, anpassbare Sprachende-Erkennung/Empfindlichkeit und maximale Dauer. Zwei Sekunden Puffer und 1,2 Sekunden Stille sind vorläufige Ausgangswerte. |
| Audiowiedergabe | Bei Musik/Streams ansprechbar bleiben; eigene Töne berücksichtigen, Sprachausgabe per Stopp unterbrechen, optionale vorübergehende Lautstärkeabsenkung. Echounterdrückung praktisch optimieren. |
| Ausgabe | Lokal; knapp als Standard, still/gesprächig wählbar. Rückfragen/Bestätigungen/Probleme sprechen, einfache Erfolge per Ton. |

## 3. Plattform, Inferenz und Kontext

| Punkt | Beschluss |
|---|---|
| Plattformadapter | OS-Funktionen kapseln, Windows zuerst; tatsächliche Fähigkeiten/Berechtigungen melden. |
| Modellbackend | llama.cpp zuerst, lokaler Server; Modell- und Backendadapter austauschbar. Transformers möglicher alternativer Weg. |
| Hardware | Unterstützte Beschleunigung/Quantisierung automatisch wählen, manuell übersteuerbar, aktiven Zustand und CPU-Fallback anzeigen, pro Gerät speichern. |
| Aktionsvertrag | Modellantwort normalisieren und strikt typisieren; Parameter/Ziel/Freigabe prüfen, ungültige Antworten zurückweisen, begrenzte Korrekturversuche. Versionen nachvollziehbar halten. |
| Grounding | Direkte Schnittstellen → Accessibility → visuelle Fallbacks. Semantische Elementaktionen nutzen, wenn vorhanden. |
| Bildschirmbedarf | Automatisch nach Bedarf einschließlich Nachforderung. on_wake/on_speech_end/both als manuelle Optionen erhalten. |
| Monitorbezug | Angesprochenes/aktives Fenster, zusätzlich Zeigekontext; Mehrdeutigkeit klären, festen Monitor manuell wählen können. |
| Capturevertrag | ID, Zeit, Fenster/Monitor, Grenzen und Bildtransformationen mit Cursorbezug; jede Aktion eindeutig an den Kontext binden. |
| DPI und Texteingabe | Mehrmonitorbetrieb, negative Offsets, gemischte Skalierungen und Unicode berücksichtigen; passende Windows-Eingabewege vorsehen. |
| SoM | Bedarfsgesteuerte interne Elementkennungen/Bildmarkierungen; optional sichtbar im Übungs-/Debug-Modus. |
| Klickvorschau | Für visuelle Ziele standardmäßig kurz an, Dauer einstellbar/abschaltbar; Overlays aus Analysebildern ausblenden. |
| Browser | Grundbedienung ohne Erweiterung. Erste optionale Erweiterung **Firefox**, übrige Browser später. Mehrere Profile/Ziele und Verbindungsstatus berücksichtigen. |

## 4. Ausführung und Sicherheit

- Mehrstufige Aufträge Schritt für Schritt mit Ziel-, Zustands- und Erfolgskontrolle. Nach UI-Änderungen neu prüfen; auch vor Texteingabe den Eingabefokus nachweisen.
- Alltagsbedienung direkt. Folgenreiche Schritte wie Senden/Kaufen/Löschen/Verwerfen und sensible Einstellungen brauchen eine konkrete Bestätigung.
- Bestätigung per Sprache oder Panel, gebunden an Aktion/Ziel/Inhalt, mit Verfallszeit. Änderungen brauchen erneute Freigabe.
- Globaler Not-Aus und Sprachstopp; begrenzte Schritte, Laufzeiten und Wiederherstellungsversuche. Abgebrochene Aufträge bleiben abgebrochen, verspätete Ergebnisse verwerfen.
- Relevante manuelle Fenster-/Fokusänderung unterbricht UI-Ausführung und löst neue Prüfung aus. Ausgeführte Teilschritte im Verlauf zeigen.
- Produktionsfehler kontrolliert melden. Mock-Antworten nur im ausdrücklich aktivierten Entwicklungsmodus, getrennt von realen Aktionen.
- Shell-Zugriff auch über kombinierte Hotkeys/Texte/App-Starts ausschließen. Erkannte/registrierte Programme mit Geräte-Alias und geprüften Parametern. URLs nur HTTP(S).
- Bildschirm-/Plugininhalte sind Daten und erteilen keine Anweisungsbefugnisse. Richtlinien im Executor durchsetzen.
- Lokales Panel und Integrationsverbindungen authentifizieren; Loopback, Sitzungstoken, Host-/Origin-/CSRF-/CORS-/WebSocket-Prüfungen.

## 5. Datenschutz, Oberfläche und Funktionen

| Punkt | Beschluss |
|---|---|
| Speicherung | Audio/Bilder standardmäßig RAM; Sitzungsverlauf. Dauerhafte Historie/Debug-Daten nur ausdrücklich aktiviert, begrenzt und löschbar. |
| Ausschlüsse | Anwendungen/Fenster vor Capture ausschließen; benötigten gesperrten Bildkontext verständlich erklären. |
| Oberfläche | Tray und lokales Web-Panel für Status, Einstellungen, Verlauf, Profile, Makros und Plugins. |
| Setup | Mikrofon, PTT, Modelle/Laufzeit samt Downloadfortschritt/lokalen Alternativen, Hardware, Berechtigungen und Probebefehl; Wake-Word-Einrichtung nach Verfügbarkeit. |
| Profile | Wählbare Unterordner im Programmordner für Benutzerprofile und Modelle, Standard-/Geräteprofile, Import/Export mit Neuzuordnung unpassender Geräte/Pfade. |
| Kurzzeitgedächtnis | Standardmäßig aktiv, begrenzt und flüchtig; Ziele erneut prüfen; „Vergiss den Kontext“. |
| Diktieren | Expliziter Modus, Satzzeichen/Unicode, klar reservierte Steuerbefehle, Pause bei Eingabezielwechsel; Absenden separat bestätigen. |
| Lesen/Erklären | Auswahl, Fenster oder Cursorbereich vorlesen/zusammenfassen/erklären; Text/Accessibility bevorzugen und Datenschutz beachten. |
| Medien | Relative/genaue Lautstärke, gezielte Anwendungen/Wiedergabequellen; bei Mehrdeutigkeit nachfragen. |
| Makros/Szenen | Benannte Abläufe, Panelbearbeitung, Import/Export, Gerätebindung; Sprachbeschreibung liefert geprüften Entwurf; identische Sicherheitsregeln. |
| Plugins | Einzeln aktivierbar, Aktionen/Zugriffe beschrieben; nur verfügbare aktive Tools anbieten. Eigene Integrationen nutzen denselben Vertrag. |
| Korrekturen | Freiwillige lokale Testfälle; Audio/Bilder separat freigeben. Alias-/Makro-Vorschläge bestätigen. |
| Übungsmodus | Nächste Aktion/Ziel/Bedienweg zeigen, erst nach ausdrücklicher Freigabe ausführen. |
| Verteilung | Reproduzierbares Python-Paket, optionale Komponenten, geführte Einrichtung, später Windows-Installer. |

## 6. Begleitende Qualität

Jede Funktion während der Umsetzung ausprobieren. Konfiguration, Transformationen, Aktionsvalidierung, Bestätigung und Abbruch automatisiert prüfen. Bekannte Fehler als Regressionen aufnehmen. Modelltests bewerten Antwortformat UND tatsächliches Ergebnis, Latenz und Speicher.

CI für plattformunabhängige Teile auf Windows/Linux/macOS; echte Plattformbedienung auf dem jeweiligen System prüfen. Keine Kompatibilität allein aus Mock-Tests ableiten. Abhängigkeiten mit pyproject.toml/uv-Lockfile reproduzierbar machen.

## 7. Einordnung der ursprünglichen Vorschläge

- Frühere §2 Wake Word: austauschbare Quelle beschlossen; persönliche Stimmerkennung optional.
- Frühere §3 Portabilität: Windows zuerst, Plattformadapter, Profile/Setup/Paketierung/CI beschlossen.
- Frühere §4.1–4.3: Accessibility/SoM, optionale Browser-Erweiterung und Kontext nach Bedarf übernommen; **Firefox zuerst**.
- Frühere §4.4: llama.cpp als erster Backendweg beschlossen. Laufzeit/Beschleunigung/Quantisierung trennen. Modellnative Tool-Formate im Adapter normalisieren; kompatibles Constrained Decoding ersetzt keine Validierung. Aussagen wie „int4 braucht immer bitsandbytes“ sind keine Architekturvorgabe.
- Frühere §4.5–4.7: Aktionskontrolle, Datenschutz/Sicherheit, DPI, genaue Lautstärke und deutschsprachige Bedienung übernommen. Keine bloße Regel „ein Klick, danach ungeprüft tippen“.
- Frühere §5 Feature-Ideen: Sprachausgabe, Vorschau, Sprachbestätigung, Kurzzeitgedächtnis, Makros, Lesen, Diktieren, Plugins und Korrekturen aufgenommen.
- Frühere §6 Modell-Spike: durch begleitende Erprobung ab erstem Durchstich ersetzt.
- Frühere §7 offene Fragen: Browser optional/Firefox zuerst; llama.cpp zuerst; Wake-Word-Quelle austauschbar mit vorhandenem Modell zum Einstieg.
- Zusätzliche Analyse: Kontextbindung, Ergebnisprüfung, Unicode/Mehrmonitor-Eingabepfad, PTT-Ende beim Loslassen, strikter Aktionsvertrag, begrenzte Fehlerbehandlung und kein stiller Mock-Fallback aufgenommen.
- Dokumentationskorrekturen: kein ausführbarer Quickstart vor Code, kein verpflichtendes Doppelbild, keine behauptete vorhandene „Computer“-Gewichtsdatei, Lizenz-/Versions-/Quellenhinweise. ONNX-Dateien können künftig über einen gezielten Assets-Pfad versioniert werden.

## 8. Bewusst spätere Ausbauten

- Weitere Browser nach Firefox und weitere Betriebssysteme nach Windows.
- Komfortable Community-Plugin-Installation.
- Eigene/verbesserte Wake-Word-Modelle bei Bedarf.
- Portable Ausgabe und optionales Modelltraining auf freigegebenen Daten.
- Weitere Inferenzadapter bei konkretem Bedarf.

Diese Punkte sind eingeplant bzw. als spätere Optionen vorgemerkt; sie sind keine bereits vorhandenen Funktionen. Technische Kandidaten, konkrete Modellquellen/Lizenzen, Backend-Kompatibilität und sinnvolle Standardgrenzen werden bei der Umsetzung geprüft. Änderungen an Produktbeschlüssen ausdrücklich festhalten.
