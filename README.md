# 🌊 ComputerFlow

> **Intelligente, lokale Sprach- und Vision-Steuerung für den PC – angetrieben von Liquid AI (LFM3-Omni-2B).**  
> *"Computer, wechsle auf den Twitch-Tab von Papaplatte."*

[![Status: Conception & Prototype](https://img.shields.io/badge/Status-Concept%20%26%20Prototype-blue.svg)](https://github.com/AntaresTerran/ComputerFlow)
[![Wake Word](https://img.shields.io/badge/Wake%20Word-Computer-red.svg)](https://github.com/AntaresTerran/ComputerFlow)
[![Architecture](https://img.shields.io/badge/Model-LFM3--Omni--2B-purple.svg)](https://liquid.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 💡 Über das Projekt

**ComputerFlow** ist ein universeller, lokaler Desktop-Assistent im Star-Trek-Stil.  
Inspiriert von den **Liquid Foundation Models (LFM)** von Liquid AI nutzt ComputerFlow das kompakte, hocheffiziente **LFM3-Omni-2B**-Modell, um Sprache und Bildschirminhalte gleichzeitig in Echtzeit auf dem eigenen Rechner zu verarbeiten – **100 % lokal, extrem latenzarm und vollkommen privat**.

### Kernidee & Alleinstellungsmerkmale
1. **Kultiges Star-Trek Wake Word („Computer“) & Nahtloser Audio-Ringbuffer:**  
   Aktivierung über das leichtgewichtige Wake-Word *„Computer“* (via `openWakeWord`) oder per Push-to-Talk (z. B. CapsLock / Maustaste). Ein permanenter **2-Sekunden-Audio-Ringbuffer** sorgt dafür, dass flüssig gesprochene Sätze ohne Pause (*„Computer, mach Musik leiser“*) keine Silbe verlieren. Optionaler Feedback-Chirp (LCARS-Stil) bestätigt den Trigger sofort.
2. **Snapshot-on-Demand Vision & Cursor-Kontext:**  
   Kein ressourcenfressender 60-FPS-Videostream! ComputerFlow nimmt standardmäßig zwei Screenshots des aktiven Bildschirms in Millisekunden auf (`snapshot_timing: "both"`): einen beim Wake-Word für den Bildschirmkontext und einen am Satzende für die aktuelle Mauszeiger-Position (*„Computer, klicke hier drauf“*). LFM3-Omni analysiert Audio + Bild simultan.
3. **Präzises Multi-Monitor & High-DPI Grounding (Normalized `[0..1000]` + Set-of-Marks):**  
   Statt fehleranfälliger Roh-Pixel nutzt ComputerFlow normalisierte `[0..1000]`-Koordinaten, die DPI-aware exakt auf den jeweiligen Monitor zurückgerechnet werden. Optional zeichnet ein **Set-of-Marks (SoM)** Overlay nummerierte Badges auf UI-Elemente, um die Trefferquote eines 2B-Modells selbst bei winzigen Buttons drastisch zu erhöhen.
4. **Action-Chaining & Native OS-Reflexe:**  
   Das Modell kann mehrstufige Aktionsketten in einem Durchlauf ausgeben (z. B. *Suchfeld klicken -> Text tippen -> Enter drücken*) und bevorzugt für Systembefehle (Mediensteuerung, Lautstärke, Fensterfokus) schnelle, verlässliche OS-APIs (`pywinctl`, Media-Keys) vor reinen Mausklicks.
5. **Universell, Portabel & Zentrales Control-Panel:**  
   Läuft auf Windows, Linux und macOS. Hardware-Auto-Detection nutzt CUDA auf Gaming-PCs und schaltet auf Laptops automatisch auf CPU/NPU/Quantisierung um – gesteuert über ein modernes System-Tray- & Web-Dashboard.

---

## 🏛️ System-Architektur

```
┌────────────────────────────────────────────────────────┐
│                   Mikrofon & Audio                    │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
           [ 1. Ebene: Trigger & Ring-Buffer ]
           - openWakeWord: Erkennt "Computer" (< 1% CPU)
           - Alternativ: Push-to-Talk (z.B. CapsLock)
           - 2s Rolling Ring-Buffer verhindert abgeschnittene Wörter
           - VAD (Voice Activity Detection): Erkennt Satzende
           - Feedback-Chirp (LCARS-Stil) bestätigt Trigger
                            │
           ┌────────────────┴────────────────┐
           │                                 │
           ▼                                 ▼
   [ Audio-Segment ]             [ 2. Ebene: Snapshot-on-Demand ]
   Sprachaufnahme des             Ultraschneller Screenshot via `mss`
   Befehls (WAV-Puffer)           (beim Wake-Word + am Satzende)
                                  + Mauszeiger-Kontext & optionales SoM-Overlay
           │                                 │
           └────────────────┬────────────────┘
                            │
                            ▼
           [ 3. Ebene: Brain / LFM3-Omni-2B ]
           - Verarbeitet Audio + Screen Snapshot + Cursor-Position
           - Gibt strukturiertes JSON mit Action-Chaining &
             normalisierten [0..1000] Koordinaten aus:
             `{"actions": [{"type": "click", "x_norm": 420, "y_norm": 85}]}`
                            │
                            ▼
           [ 4. Ebene: Actuator & Execution ]
           - High-DPI & Multi-Monitor Koordinaten-Transformation
           - Native OS-Reflexe (Window-Focus, Media-Keys, Hotkeys)
           - Safety Guardrails & Safe-Mode Check
                            │
                            ▼
           [ 5. Control Panel & System Tray ]
           - Web/GUI Dashboard zur Konfiguration & Statusanzeige
```

---

## 🎛️ Settings- & Control-Panel

ComputerFlow verfügt über ein übersichtliches Panel (lokale Web-UI + System-Tray-Icon):

* **Audio & Trigger:**
  * Auswahl des Eingabegeräts, Ring-Buffer-Länge, Wake-Word Empfindlichkeit & Feedback-Chirp (LCARS-Stil).
  * Push-to-Talk Tastenzuweisung.
* **Vision & Grounding:**
  * Monitorauswahl (`active_cursor`, Hauptmonitor oder fester Index).
  * Snapshot-Timing (`both` als Standard: Kontext beim Wake-Word + Cursor-Position am Satzende; alternativ nur `on_wake` oder `on_speech_end`).
  * Optionales Set-of-Marks (SoM) UI-Overlay für maximale Klick-Präzision.
* **Modell & Hardware:**
  * Backend-Auswahl: CUDA (Nvidia), DirectML, CPU/NPU.
  * Quantisierungsstufe (z. B. 4-bit für Laptops, 8-bit / FP16 für dGPU).
* **Sicherheit & Guardrails:**
  * Bestätigungsdialoge für destruktive Aktionen (z. B. Schließen von ungespeicherten Dokumenten).
  * Shell-Befehle werden aus Sicherheitsgründen bewusst nicht unterstützt.
* **Live-Log & History:**
  * Historie der letzten Befehle, Snapshots (mit eingezeichnetem Klickpunkt) und ausgeführten Aktionen zur einfachen Fehlersuche.

---

## 📁 Geplante Projektstruktur

```
ComputerFlow/
├── config.example.yaml        # Vorlage für Einstellungen
├── config.yaml                # Lokale Konfiguration (nicht in Git)
├── requirements.txt           # Python-Abhängigkeiten
├── README.md                  # Projektübersicht
├── LICENSE                    # MIT-Lizenz (gilt für den Code, nicht für Modellgewichte)
├── AGENT_SPEC.md              # Detaillierte Spezifikation für KI-Entwicklungsagenten
├── VERBESSERUNGEN.md          # Gesammelte Analyse, Verbesserungsvorschläge & Ideen
│
├── computerflow/
│   ├── __init__.py
│   ├── main.py                # Haupteinstiegspunkt & Orchestrator (inkl. DPI-Awareness)
│   │
│   ├── core/                  # Kernlogik & Pipeline
│   │   ├── config_manager.py  # Laden & Validieren von config.yaml (Pydantic)
│   │   └── state.py           # Laufzeit-Zustand & Event-Bus
│   │
│   ├── audio/                 # Audioaufnahme, Ring-Buffer & Wake-Word
│   │   ├── wake_word.py       # openWakeWord Listener ("Computer") via sounddevice
│   │   ├── push_to_talk.py    # Tastatur-/Maus-Hook Trigger
│   │   ├── recorder.py        # Rolling Ring-Buffer + VAD Sprachaufnahme
│   │   └── feedback.py        # Feedback-Chirp (LCARS-Stil): Wake, Success, Error
│   │
│   ├── vision/                # Bildschirmerfassung & Grounding
│   │   ├── screen_capture.py  # Snapshot-on-Demand, Cursor-Tracking & DPI-Mapping
│   │   └── som_overlay.py     # Optionales Set-of-Marks Overlay für UI-Elemente
│   │
│   ├── brain/                 # LFM3-Omni Schnittstelle
│   │   ├── lfm_client.py      # Lokale Inferenz (LFM3-Omni-2B)
│   │   ├── prompt_templates.py# System-Prompts & Cursor/Monitor-Kontext
│   │   └── actions_schema.py  # Pydantic-Schema für Action-Chaining & Tool-Calls
│   │
│   ├── actuator/              # Ausführungsebene
│   │   ├── executor.py        # Routing & Sequenz-Ausführung (Action-Chaining)
│   │   ├── os_actions.py      # Native Fenstersteuerung (pywinctl), Media-Keys, Apps
│   │   └── ui_actions.py      # Norm-zu-Pixel Transformation, Maus & Tastatur
│   │
│   └── panel/                 # Settings & Control Panel
│       ├── server.py          # FastAPI / WebSocket Backend
│       ├── tray.py            # System Tray Icon (pystray)
│       └── web/               # Leichtes HTML5/CSS/JS Dashboard
│
└── tests/                     # Unit- & Integrationstests
```

---

## 🚀 Erste Schritte (Quickstart)

### Voraussetzungen
* Python 3.10+
* Git
* Mikrofon
* Optional: Nvidia GPU mit CUDA-Support (empfohlen für maximale Geschwindigkeit)

### Installation
```bash
git clone https://github.com/AntaresTerran/ComputerFlow.git
cd ComputerFlow
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp config.example.yaml config.yaml
python -m computerflow.main
```

---

## 🗺️ Roadmap & Meilensteine

- [x] **Phase 0:** Konzeption, Architektur & Repo-Setup
- [ ] **Phase 1 (MVP Trigger & Audio):** Wake-Word („Computer“), 2s Audio-Ringbuffer, VAD & Feedback-Chirp
- [ ] **Phase 2 (Vision & Brain):** High-DPI Snapshot-on-Demand, Cursor-Kontext & LFM3-Omni-2B Action-Chaining
- [ ] **Phase 3 (Actuator):** Norm-Koordinaten-Mapping, Native OS-Reflexe (`pywinctl`) & Safety Guardrails
- [ ] **Phase 4 (Control Panel):** System-Tray-App und Settings-Dashboard mit Snapshot-Inspector
- [ ] **Phase 5 (Testing & Portabilität):** Set-of-Marks (SoM) Feinschliff & Hardware-Benchmarking

---

## 🤝 Zusammenarbeit mit KI-Agenten

Für Entwickler und KI-Assistenten: Bitte lies vor dem Start die **[AGENT_SPEC.md](AGENT_SPEC.md)**. Sie enthält präzise Implementierungsdetails, Schnittstellenverträge und Coding-Guidelines für das Projekt.

Gesammelte Analyse, offene Punkte und Ideen zur Weiterentwicklung findest du in **[VERBESSERUNGEN.md](VERBESSERUNGEN.md)**.

---

## 📜 Lizenz

* **Code:** [MIT-Lizenz](LICENSE)
* **Modell:** Die Gewichte von **LFM3-Omni-2B** sind **nicht** Teil dieses Repos und unterliegen der eigenen Lizenz von Liquid AI (*LFM Open License*). Bitte die Bedingungen auf der [Hugging-Face-Modellseite](https://huggingface.co/LiquidAI/LFM3-Omni-2B) prüfen. Für die private, nicht-kommerzielle Nutzung ist sie in der Regel unproblematisch.
