# 🤖 ComputerFlow – Agent Specification & Implementation Guide

> **Zweck dieses Dokuments:** Dieses Dokument dient als verbindliche Spezifikation und Handbuch für KI-Entwicklungsagenten (z. B. Antigravity, Claude, ChatGPT), die an **ComputerFlow** arbeiten. Es definiert die Architektur, Schnittstellenverträge, Design-Entscheidungen und die nächsten konkreten Arbeitsschritte.

---

## 🎯 1. Projekt-Vision & Leitprinzipien

ComputerFlow ist ein **lokaler, multimodaler Desktop-Sprachassistent**, der durch das Wake-Word **„Computer“** aktiviert wird und Sprachbefehle in Verbindung mit einem Live-Screenshot des Bildschirms analysiert.

### Die 4 goldenen Regeln
1. **Kein Dauer-Video-Streaming:** Das System nimmt beim Auslösen des Triggers genau **einen Snapshot** auf (*Snapshot-on-Demand*). Das schont CPU/GPU und minimiert die Latenz.
2. **Plattformunabhängigkeit vor OS-Hacks:** Verwende ausschließlich Cross-Platform-Bibliotheken (`mss`, `sounddevice`, `pyautogui`, `webbrowser`, `pynput`). Keine fest verdrahteten Pfade zu Programmen auf einem einzelnen PC.
3. **Sicherheit geht vor (Safe Guardrails):** Destruktive Operationen (Dateien löschen, Shell-Befehle ausführen, ungespeicherte Fenster schließen) dürfen niemals blind ausgeführt werden.
4. **Schlankes Kern-System mit Control Panel:** Die Konfiguration erfolgt primär über ein GUI/Web-Panel oder `config.yaml`, nicht über Hardcoding im Python-Code.

---

## 📦 2. Technologie-Stack & Bibliotheken

| Bereich | Empfohlene Bibliothek / Werkzeug | Begründung |
| :--- | :--- | :--- |
| **Sprache** | Python 3.10+ | Breites KI- und OS-Ökosystem |
| **Wake Word** | `openWakeWord` | Open-Source, < 1 % CPU-Last, vortrainiertes Modell für `"computer"` verfügbar |
| **Audio I/O & VAD** | `sounddevice`, `numpy`, `webrtcvad` / `silero-vad` | Schnelle Pufferung, automatische Erkennung des Sprechendes |
| **Screen Capture** | `mss` | Ultraschnell (~5–10 ms pro Frame), plattformübergreifend |
| **Brain / Inferenz** | `transformers` / `vllm` / `llama.cpp` (Liquid LFM3-Omni-2B) | Lokale Ausführung mit CUDA / CPU Fallback |
| **Aktionen / OS** | `pyautogui`, `pynput`, `subprocess`, `webbrowser` | Tastatur, Maus, Fenster, URLs steuern |
| **Control Panel** | `fastapi`, `uvicorn`, `pystray`, `Pillow` (System-Tray + Web Dashboard) | Leichtgewichtig, modern, im Browser auf jedem Gerät anpassbar |
| **Konfiguration** | `pydantic`, `pyyaml` | Typisierte und validierte Einstellungen |

---

## 🔄 3. Datenfluss & Schnittstellen-Verträge

### Ablauf eines Sprachbefehls:
```
1. Trigger-Event:
   openWakeWord erkennt "Computer" (oder PTT gedrückt)
        │
        ├─────────────────────────────────────────┐
        ▼                                         ▼
   Audio-Recorder startet                    Screen-Capture schießt
   Sprachaufnahme bis VAD                    Snapshot: `screenshot.jpg`
   Stille meldet (z. B. 1.2s)
        │                                         │
        └────────────────────┬────────────────────┘
                             │
                             ▼
2. Brain-Anfrage:
   LFM3-Omni-2B empfängt:
   - System Prompt (JSON Schema)
   - Audio-Puffer (WAV / PCM)
   - Bild-Puffer (JPEG / PIL Image)
                             │
                             ▼
3. Brain-Antwort (Strukturiertes JSON):
   {
     "intent": "switch_browser_tab",
     "action": "click",
     "target_description": "Twitch Tab",
     "coordinates": {"x": 450, "y": 72},
     "spoken_response": "Wechsle auf Twitch."
   }
                             │
                             ▼
4. Actuator-Ausführung:
   - Prüft Sicherheitsrichtlinie
   - Führt Aktion aus (z.B. pyautogui.click(450, 72))
   - Gibt optional Audio-Feedback (TTS / Beep)
```

---

## 🛠️ 4. Modul-Spezifikationen

### A. `computerflow/audio/`
* `wake_word.py`: Läuft in einem separaten Thread. Verarbeitet Audio-Chunks in Echtzeit mit `openWakeWord`. Sobald der Konfidenzwert für `"computer"` über `wake_word_sensitivity` liegt, wird das `on_wake`-Event getriggert.
* `recorder.py`: Nimmt nach dem Trigger Audio auf, bis VAD (Voice Activity Detection) das Satzende erkennt. Gibt die Audiodaten als Byte-Stream oder temporäre WAV-Datei zurück.

### B. `computerflow/vision/`
* `screen_capture.py`:
  * Methode: `capture_active_screen(max_res=(1920, 1080)) -> PIL.Image`
  * Ermittelt den Bildschirm, auf dem sich die Maus/das aktive Fenster befindet.
  * Reskaliert das Bild proportional, um Inferenzzeit zu sparen, ohne Lesbarkeit von Text zu zerstören.

### C. `computerflow/brain/`
* `lfm_client.py`:
  * Kapselt die Inferenz des LFM3-Omni-2B Modells.
  * Unterstützt dynamische Backends: CUDA (Nvidia), DirectML oder CPU.
  * Standardisierter Output: Reines, valides JSON gemäß `actions_schema.py`.

### D. `computerflow/actuator/`
* `executor.py`:
  * Verarbeitet die Aktionen:
    * `click(x, y, button="left")`
    * `type_text(text, enter=False)`
    * `press_hotkey(keys)` (z. B. `["ctrl", "w"]`)
    * `open_url(url)`
    * `launch_app(app_name)`
    * `system_volume(delta_or_percent)`

### E. `computerflow/panel/`
* Lokales Web-Dashboard unter `http://127.0.0.1:8088`.
* System-Tray-Icon (mit `pystray`), um den Assistenten stummzuschalten, zu pausieren oder das Panel zu öffnen.
* REST-APIs zum Lesen und Schreiben der `config.yaml`.

---

## 📋 5. Konkreter Arbeitsauftrag für den nächsten Agenten

Wenn du als neuer Agent dieses Projekt fortführst, halte dich an folgende Reihenfolge:

1. **Schritt 1: Initialisiere das Grundgerüst (`computerflow/`)**
   * Erstelle die Ordnerstruktur und `requirements.txt`.
   * Implementiere `config_manager.py` mit `pydantic` zur Validierung von `config.yaml`.
2. **Schritt 2: Audio- und Trigger-Pipeline (`computerflow/audio/`)**
   * Implementiere `recorder.py` und `wake_word.py` (oder PTT-Fallback).
   * Teste die Audio-Aufnahme isoliert.
3. **Schritt 3: Screen-Capture (`computerflow/vision/`)**
   * Implementiere `screen_capture.py` mit `mss`.
4. **Schritt 4: Brain-Stub & Mock-Inference (`computerflow/brain/`)**
   * Baue eine Mock-Funktion, die Audio + Bild entgegennimmt und Test-Aktionen zurückgibt, bevor das vollständige LFM-Gewicht geladen wird.
5. **Schritt 5: Actuator & Action-Routing (`computerflow/actuator/`)**
   * Sichere Ausführung von Mausklicks und Tastaturbefehlen.
6. **Schritt 6: Settings-Panel & Tray-Icon (`computerflow/panel/`)**
   * Kleines FastAPI-Backend mit statischer HTML/Tailwind/Vue-Einstellungsseite.
