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
1. **Kultiges Star-Trek Wake Word („Computer“):**  
   Aktivierung wahlweise über das leichtgewichtige Wake-Word *„Computer“* (via `openWakeWord`) oder per Push-to-Talk (z. B. CapsLock / Maustaste).
2. **Snapshot-on-Demand Vision:**  
   Kein ressourcenfressender 60-FPS-Videostream! Beim Auslösen des Sprachbefehls nimmt ComputerFlow in Millisekunden einen Screenshot des aktiven Bildschirms auf. LFM3-Omni analysiert Audio + Bild simultan, versteht die UI-Elemente und steuert Programme ohne starre Selektoren.
3. **Universell & Portabel (Desktop & Laptop):**  
   Keine hardgecodeten Pfade. Läuft nahtlos auf Windows, Linux und macOS. Hardware-Auto-Detection nutzt CUDA auf Gaming-PCs und schaltet auf Laptops automatisch auf CPU/NPU/Quantisierung um.
4. **Zentrales Control- & Settings-Panel:**  
   Ein modernes Dashboard (Web/GUI) zur Konfiguration von Mikrofonen, Schwellenwerten, Hotkeys, Safe-Mode und Modellauslastung inklusive System-Tray-Minimierung.

---

## 🏛️ System-Architektur

```
┌────────────────────────────────────────────────────────┐
│                   Mikrofon & Audio                    │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
           [ 1. Ebene: Trigger / Wake-Word ]
           - openWakeWord: Erkennt "Computer" (< 1% CPU)
           - Alternativ: Push-to-Talk (z.B. CapsLock)
           - VAD (Voice Activity Detection): Schneidet Befehl
                            │
           ┌────────────────┴────────────────┐
           │                                 │
           ▼                                 ▼
   [ Audio-Segment ]             [ 2. Ebene: Snapshot-on-Demand ]
   Sprachaufnahme des             Ultraschneller Screenshot via `mss`
   Befehls (WAV-Puffer)           im Moment des Triggers
           │                                 │
           └────────────────┬────────────────┘
                            │
                            ▼
           [ 3. Ebene: Brain / LFM3-Omni-2B ]
           - Verarbeitet Audio + Screen Snapshot
           - Erkennt Intent & visuelle Koordinaten
           - Gibt strukturiertes JSON (Function Call) aus:
             `{"action": "click", "x": 420, "y": 85, "reason": "Twitch Tab"}`
                            │
                            ▼
           [ 4. Ebene: Actuator & Execution ]
           - Cross-Platform OS-Steuerung (Maus, Tastatur, URLs)
           - Safety Guardrails & Safe-Mode Check
                            │
                            ▼
           [ 5. Control Panel & System Tray ]
           - Web/GUI Dashboard zur Konfiguration & Statusanzeige
```

---

## 🎛️ Settings- & Control-Panel

ComputerFlow verfügt über ein übersichtliches Panel (lokale Web-UI oder schlankes Desktop-GUI), das sich ins System-Tray einnistet:

* **Audio & Trigger:**
  * Auswahl des Eingabegeräts (Headset, USB-Mikrofon, Laptop-Mic).
  * Wake-Word Empfindlichkeit & Test-Pegel.
  * Push-to-Talk Tastenzuweisung.
* **Vision & Screen:**
  * Monitorauswahl (Hauptmonitor, Multimonitor oder dynamisch aktiver Fokus).
  * Auflösungsskalierung & Bildkompression für schnellste Inferenz.
* **Modell & Hardware:**
  * Backend-Auswahl: CUDA (Nvidia), DirectML, CPU/NPU.
  * Quantisierungsstufe (z. B. 4-bit für Laptops, 8-bit / FP16 für dGPU).
* **Sicherheit & Guardrails:**
  * Bestätigungsdialoge für destruktive Aktionen (z. B. Schließen von ungespeicherten Dokumenten oder Ausführen von Shell-Befehlen).
* **Live-Log & History:**
  * Historie der letzten Befehle, Snapshots und ausgeführten Aktionen zur einfachen Fehlersuche.

---

## 📁 Geplante Projektstruktur

```
ComputerFlow/
├── config.example.yaml        # Vorlage für Einstellungen
├── config.yaml                # Lokale Konfiguration (nicht in Git)
├── requirements.txt           # Python-Abhängigkeiten
├── README.md                  # Projektübersicht
├── AGENT_SPEC.md              # Detaillierte Spezifikation für KI-Entwicklungsagenten
│
├── computerflow/
│   ├── __init__.py
│   ├── main.py                # Haupteinstiegspunkt & Orchestrator
│   │
│   ├── core/                  # Kernlogik & Pipeline
│   │   ├── config_manager.py  # Laden & Validieren von config.yaml
│   │   ├── state.py           # Laufzeit-Zustand & Event-Bus
│   │
│   ├── audio/                 # Audioaufnahme & Wake-Word
│   │   ├── wake_word.py       # openWakeWord Listener ("Computer")
│   │   ├── push_to_talk.py    # Tastatur-/Maus-Hook Trigger
│   │   └── recorder.py        # VAD & Sprachaufnahme
│   │
│   ├── vision/                # Bildschirmerfassung
│   │   └── screen_capture.py  # Snapshot-on-Demand via mss
│   │
│   ├── brain/                 # LFM3-Omni Schnittstelle
│   │   ├── lfm_client.py      # Lokale Inferenz (LFM3-Omni-2B)
│   │   ├── prompt_templates.py# System-Prompts & JSON-Schemas
│   │   └── actions_schema.py  # Definition gültiger Tool-Calls
│   │
│   ├── actuator/              # Ausführungsebene
│   │   ├── executor.py        # Routing der Aktionen
│   │   ├── os_actions.py      # App-Starts, Systemlautstärke, Shortcuts
│   │   └── ui_actions.py      # Maus-Klicks, Tastatureingaben (pyautogui)
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
- [ ] **Phase 1 (MVP Trigger & Audio):** Wake-Word („Computer“) + PTT + Audio-Pufferung
- [ ] **Phase 2 (Vision & Brain):** Snapshot-on-Demand + Anbindung LFM3-Omni-2B Function Calling
- [ ] **Phase 3 (Actuator):** Sichere Ausführung von UI- und OS-Aktionen
- [ ] **Phase 4 (Control Panel):** System-Tray-App und Settings-Dashboard
- [ ] **Phase 5 (Testing & Portabilität):** Hardware-Benchmarking auf Laptop & Desktop

---

## 🤝 Zusammenarbeit mit KI-Agenten

Für Entwickler und KI-Assistenten: Bitte lies vor dem Start die **[AGENT_SPEC.md](AGENT_SPEC.md)**. Sie enthält präzise Implementierungsdetails, Schnittstellenverträge und Coding-Guidelines für das Projekt.
