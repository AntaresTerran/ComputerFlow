# 🌊 ComputerFlow

Ein geplanter lokaler Sprach- und Bildschirmassistent für den Desktop.

> „Computer, wechsle auf den Twitch-Tab von Papaplatte.“

**Stand: Konzept beschlossen, Implementierung noch nicht begonnen.** Das Repository enthält Planung und Konfigurationsvorlage. Es gibt noch keinen ausführbaren Assistenten und keine veröffentlichte Anwendungsversion.

## Ziel und Arbeitsweise

ComputerFlow soll Sprache, Fensterinformationen und bei Bedarf Bildschirmbilder zu ausführbaren Desktop-Aufträgen verbinden. Die Verarbeitung bleibt lokal. Windows wird zuerst umgesetzt; Linux und macOS bleiben Teil des Zielumfangs. Unterschiedliche Hardware wird über Plattformadapter, automatische Auswahl und Geräteprofile berücksichtigt.

Wir beginnen mit Push-to-Talk und ergänzen das Wake Word unmittelbar danach. Tests begleiten die Umsetzung; eine separate vorgeschaltete Modelltestphase entfällt.

## Beschlossener Funktionsumfang

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

## Entwicklungsunterlagen und Einrichtung

- [AGENT_SPEC.md](AGENT_SPEC.md): Verbindliche Architektur und Ausführungsverträge.
- [PROJEKTENTSCHEIDUNGEN.md](PROJEKTENTSCHEIDUNGEN.md): Beschlossene Projekteigenschaften, Funktionsumfang und spätere Ausbauten.
- [config.example.yaml](config.example.yaml): Geplantes Konfigurationsschema, noch keine implementierte API.

Ein ausführbarer Quickstart folgt mit 0.0.1. Paketstruktur, pyproject.toml, uv-Lockfile und CI werden mit der Implementierung erstellt. Die Requirements sind vorläufige Bibliothekskandidaten, keine getestete Installationskombination. Der optionale Transformers-Weg ist in requirements-transformers.txt getrennt.

Der spätere Setup-Assistent richtet Mikrofon, Trigger und lokale Inferenz ein, zeigt Downloads und akzeptiert vorhandene Modelle. Ein Windows-Installer ist eingeplant. Latenz, Speicherbedarf und Plattformkompatibilität sind noch nicht gemessen.

## Lizenz

Code: [MIT](LICENSE). Modelle und Wake-Word-Gewichte haben eigene Lizenzen und werden mit Herkunft und Revision behandelt. Siehe die offiziellen Quellen für [LFM3-Omni-2B](https://huggingface.co/LiquidAI/LFM3-Omni-2B) und die geplante [GGUF-Variante](https://huggingface.co/LiquidAI/LFM3-Omni-2B-GGUF).
