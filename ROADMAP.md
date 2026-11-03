# ComputerFlow – Roadmap

Beschlossener Planungsstand: 3. November 2026. **Aktuell: Konzeptstand, noch kein Release.**

## Leitlinien

- Niedrig beginnen: erster nutzbarer Entwicklungsstand **0.0.1**. Die frühen Versionen dürfen experimentell sein.
- Jede Etappe bündelt zusammengehörige Funktionen und liefert einen nutzbaren Stand. Einzelne Module und Fehlerbehebungen sind Aufgaben innerhalb einer Etappe.
- Implementierung und Tests laufen gemeinsam. Keine separate vorgeschaltete Modelltestphase. Fehlerkorrekturen können als 0.0.x-Patchstände erscheinen; die Tabelle beschreibt Zielmeilensteine, keinen Zwang zu einer Version je Änderung.
- Push-to-Talk zuerst; Wake Word direkt danach. Größere Oberfläche und Zusatzfunktionen dürfen diesen Einstieg nicht verzögern.
- Windows zuerst mit gemeinsamen Plattformverträgen. Firefox ist der erste Browser mit optionaler Erweiterung; Grundbedienung bleibt erweiterungsunabhängig.
- Die Beschlüsse in AGENT_SPEC.md und PROJEKTENTSCHEIDUNGEN.md gelten über alle Etappen. Verschobene Funktionen bleiben im Zielumfang. Sicherheits- und Datenschutzregeln gelten ab ihrer ersten betroffenen Funktion.
- Keine Kalendertermine und keine automatische Freigabe anhand einer Versionsnummer. Maßgeblich ist nachgewiesenes Verhalten; noch fehlende Fähigkeiten bleiben sichtbar.

## Frühe Entwicklungsstände

### 0.0.1 – Erster nutzbarer Windows-Durchstich

**Ergebnis:** Ein gesprochener Auftrag führt lokal eine erste echte Systemaktion aus.

- Python-Paket, Konfiguration und gemeinsame Plattform-/Inferenzschnittstellen; llama.cpp als erster lokaler Modellweg.
- Push-to-Talk über rechte Strg-Taste, erstes Audiohandling, Fensterwechsel und grundlegende Medienaktionen.
- Strikter Aktionsvertrag, minimale Status-/Fehleranzeige und Abbruchmöglichkeit. Kein stiller Mock-Fallback; zunächst kleiner Umfang erlaubter Aktionen.
- Begleitende Tests für Konfiguration, Aktionsvalidierung und den tatsächlichen Durchstich; Versions-/Laufzeitinformationen erfassen.

**Erreicht, wenn:** PTT-Aufträge auf Windows echte erlaubte Aktionen auslösen; ungültige Antworten, Modellfehler und Abbrüche kontrolliert behandelt werden. Bereits hier Rückfragen/Freigaben für vorhandene betroffene Aktionen ermöglichen.

### 0.0.2 – „Computer“ und flüssige Audiointeraktion

**Ergebnis:** ComputerFlow lässt sich zusätzlich freihändig aktivieren.

- Austauschbare Wake-Word-Quelle mit erstem vorhandenen „Computer“-Modell, Ringbuffer, einstellbarer Empfindlichkeit und Sprachende-Erkennung.
- PTT bleibt verfügbar; Halte-/Umschaltmodus und freie Tastenbelegung. Aufnahmegrenzen und Aktivierungsfeedback.
- Lokale knappe Audioantworten, sprachlicher Abbruch, Berücksichtigung eigener Töne und unterbrechbare Ausgabe.
- Optionaler persönlicher Verifier und Lautstärkeabsenkung; praktische Erprobung mit Lautsprechern, Musik und Streams.

**Erreicht, wenn:** Fließend gesprochene Aufträge einschließlich Satzanfang ankommen, Trigger konfigurierbar sind und Stopp auch während Verarbeitung/Ausgabe funktioniert.

### 0.0.3 – Zuverlässige Desktop- und UI-Bedienung

**Ergebnis:** ComputerFlow kann sichtbare Oberflächen kontextbezogen und kontrolliert bedienen.

- Direkte Aktionen, Windows-Accessibility und visuelle Fallbacks; Unicode-Eingabe und präzise System-/Anwendungslautstärke.
- Bedarfsgesteuerter Bildkontext, Fenster-/Cursorbezüge, Mehrmonitor-/DPI-Mapping, kontextgebundene Elementkennungen und SoM.
- Schrittweise Ausführung mit Fokus-/Ziel-/Erfolgskontrolle, Rückfragen, konkreten Bestätigungen und begrenzter Wiederherstellung.
- Klickvorschau, Übungsmodus, manuelle Übernahme und Verwerfen verspäteter Ergebnisse. Aufnahme-Ausschlüsse und sichere Text-/Hotkey-/App-Kombinationen.

**Erreicht, wenn:** Repräsentative Aufträge auch bei Fokuswechseln, mehreren Monitoren und mehrdeutigen Zielen geprüft funktionieren. Browser-Grundbedienung wird bereits ohne Erweiterung erprobt.

### 0.0.4 – Firefox im Alltag

**Ergebnis:** Die optionale Firefox-Erweiterung ergänzt die allgemeine Browserbedienung um direkte Tab-Aktionen.

- Authentifizierte lokale Verbindung, Tab-Titel/URLs und gezieltes Wechseln.
- Mehrere Fenster, Browserprofile und ähnliche Tab-Namen mit Kontextprüfung/Rückfragen berücksichtigen.
- Verbindungsstatus und Fähigkeiten anzeigen; bei fehlender Erweiterung allgemeine Bedienwege verwenden.

**Erreicht, wenn:** Der Beispielauftrag zum Twitch-Tab praktisch funktioniert und Firefox ohne Erweiterung weiterhin über die Grundbedienung ansprechbar bleibt.

### 0.0.5 – Einrichtung und Kontrolle

**Ergebnis:** ComputerFlow lässt sich ohne manuelle Bearbeitung einzelner Konfigurationsdateien einrichten und bedienen.

- Vollständigeres Tray und geschütztes lokales Web-Panel mit Einstellungen, Status, Sitzungsverlauf und Snapshot-/Zielinspektion nach Datenschutzfreigabe.
- Setup für Mikrofon, Trigger, lokale Modelle/Laufzeit und Berechtigungen; Downloadfortschritt und vorhandene Installationen.
- Automatische unterstützte Hardware-/Quantisierungsauswahl, manuelle Übersteuerung und sichtbarer CPU-Fallback.
- Benutzerspezifische Speicherorte, Geräteprofile, Import/Export und optionale begrenzte dauerhafte Historie/Debug-Daten.

**Erreicht, wenn:** Eine neue Windows-Installation über die geführte Einrichtung bis zum Probebefehl gelangt und Einstellungen sowie Lösch-/Aufbewahrungsfunktionen bedienbar sind.

### 0.0.6 – Diktieren und Bildschirmassistenz

**Ergebnis:** ComputerFlow hilft beim Schreiben, Lesen und bei Folgeaufträgen.

- Diktiermodus mit Satzzeichen/Unicode, klaren Steuerbefehlen und Prüfung des Eingabeziels.
- Ausgewählte oder kontextbezogene Inhalte vorlesen, zusammenfassen und erklären.
- Zeitlich begrenztes Kurzzeitgedächtnis mit „Vergiss den Kontext“, erneuter Zielprüfung und Rückfragen.
- Ausgabemodi still/knapp/gesprächig sowie durchgängige Sprach-/Panelinteraktion.

**Erreicht, wenn:** Schreiben, Lesen und eindeutige Folgeaufträge praktisch nutzbar sind; Fokuswechsel und Aufnahme-Ausschlüsse korrekt behandelt werden.

### 0.0.7 – Wiederverwendbare Abläufe und Integrationen

**Ergebnis:** Eigene Arbeitsabläufe lassen sich speichern und ComputerFlow lässt sich gezielt erweitern.

- Makros/Szenen mit Panelbearbeitung, Import/Export, Gerätebindung und geprüften Entwürfen aus Beschreibungen.
- Einzeln aktivierbare Plugins mit beschriebenen Aktionen/Zugriffen; eigene Integrationen verwenden denselben Vertrag.
- Freiwillig gespeicherte Fehlerkorrekturen als lokale Testfälle; bestätigte Alias-/Makro-Vorschläge.
- Bestätigungen, Zustandsprüfung und Abbruch gelten auch innerhalb gespeicherter Abläufe und Plugins.

**Erreicht, wenn:** Ein mehrstufiger Alltagsablauf gespeichert und erneut kontrolliert ausgeführt werden kann; deaktivierte oder nicht verfügbare Integrationen liefern keine ausführbaren Modelltools.

## Weitere 0.x-Etappen

| Zielbereich | Schwerpunkt | Nutzbarer Abschluss |
|---|---|---|
| **0.1.x – Erste zusammenhängende Alpha** | Frühe Funktionen integrieren, Regressionen beheben, Installation auf weiteren Windows-Rechnern erproben | Zusammenhängender Windows-Alltagseinsatz mit dokumentierten Grenzen |
| **0.2.x – Verteilung und Robustheit** | Windows-Installer, Modell-/Abhängigkeitseinrichtung, Wiederanlauf und verständliche Diagnose vertiefen | Andere Nutzer können installieren, einrichten und Probleme nachvollziehbar melden |
| **0.3.x – Weitere Browser und Erweiterungen** | Chrome/Edge und weitere Browser priorisiert ergänzen; komfortablere Community-Plugin-Installation | Zusätzliche Integrationen mit denselben Kontrollen und klarer Fähigkeitenanzeige |
| **0.4.x – Linux** | Plattformadapter, Berechtigungen, Audio und Desktopintegration; X11/Wayland getrennt prüfen | Unterstützte Linux-Umgebungen sind real getestet und dokumentiert |
| **0.5.x – macOS** | Plattformadapter, Berechtigungen, Audio und Desktopintegration | Unterstützte macOS-Konfigurationen sind real getestet und dokumentiert |
| **Weitere 0.x-Versionen** | Plattformübergreifende Alltagstauglichkeit, Leistungsoptimierung, Installationspflege und Rückmeldungen | Nachgewiesene Stabilität des vereinbarten Funktionsumfangs |

Diese späteren Bereiche sind gröber geplant. Reihenfolge und Umfang können anhand realer Umsetzungsergebnisse angepasst werden; Änderungen an beschlossenen Produktfunktionen werden ausdrücklich festgehalten.

## Langfristige Ausbauten

- Zusätzliche Modell-/Backendadapter, wenn sie einen konkreten Bedarf lösen.
- Eigene bzw. verbesserte Wake-Word-Modelle.
- Portable Ausgabe.
- Optionales Modelltraining auf ausdrücklich freigegebenen Korrekturdaten.

Diese Ausbauten sind keine stillschweigenden Voraussetzungen für den ersten nutzbaren Stand.

## Wann 1.0 sinnvoll ist

1.0 bleibt bewusst ohne Datum und ohne vorgezogene Versionsleiter bis 0.9. Voraussetzung sind ein stabiler vereinbarter Kernumfang, nachvollziehbar geprüfte unterstützte Plattformen und Integrationen, verlässliche Bestätigung/Abbruch/Datenschutzfunktionen sowie reproduzierbare Installation und brauchbare Dokumentation.

Ein erfolgreicher Einzeltest oder eine vollständig abgehakte Funktionsliste allein genügt nicht. Bis dahin können so viele 0.x-Stände entstehen, wie die Alltagserprobung erfordert.
