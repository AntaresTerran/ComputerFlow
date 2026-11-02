# 🤖 ComputerFlow – Agent Specification & Implementation Guide

> **Zweck dieses Dokuments:** Dieses Dokument dient als verbindliche Spezifikation und Handbuch für KI-Entwicklungsagenten (z. B. Antigravity, Claude, ChatGPT), die an **ComputerFlow** arbeiten. Es definiert die Architektur, Schnittstellenverträge, Design-Entscheidungen und die konkreten Arbeitsschritte.

---

## 🎯 1. Projekt-Vision & Leitprinzipien

ComputerFlow ist ein **lokaler, multimodaler Desktop-Sprachassistent**, der durch das Wake-Word **„Computer“** aktiviert wird und Sprachbefehle in Verbindung mit einem Live-Screenshot des Bildschirms analysiert.

### Die 6 goldenen Regeln
1. **Kein Dauer-Video-Streaming:** Das System nimmt beim Auslösen eines Befehls gezielt **einen Snapshot** auf (*Snapshot-on-Demand*). Das schont CPU/GPU und minimiert die Latenz.
2. **Nahtloser Audio-Ringbuffer:** Da Nutzer nach dem Wort *„Computer“* oft ohne Pause weitersprechen (*„Computer, wechsle auf Twitch“*), hält der Audio-Stream einen permanenten Ringbuffer (z. B. 2 Sekunden). Beim Trigger wird direkt im Puffer geschnitten, damit keine Silbe verloren geht.
3. **Normalisierte Koordinaten (`[0..1000]`) & High-DPI Awareness:** Das Vision-Modell gibt niemals rohe Bildschirm-Pixel aus, sondern normalisierte Koordinaten (`x_norm`, `y_norm` im Bereich `0` bis `1000`). Der Actuator rechnet diese unter Berücksichtigung von Windows-DPI-Scaling und Multi-Monitor-Offsets (`left`, `top`, `width`, `height`) exakt auf physische OS-Koordinaten um.
4. **Native OS-Reflexe vor blinden Mausklicks:** Wann immer eine Aktion über native OS-/Fenster-APIs (`pywinctl`, Media-Keys, Shortcuts) ausgeführt werden kann (z. B. Fenster fokussieren, Lautstärke ändern, Play/Pause), werden diese gegenüber fehleranfälligen Mausklicks bevorzugt.
5. **Sicherheit geht vor (Safe Guardrails):** Destruktive Operationen (Dateien löschen, Shell-Befehle ausführen, ungespeicherte Fenster schließen) dürfen niemals blind ausgeführt werden.
6. **Schlankes Kern-System mit Control Panel:** Die Konfiguration erfolgt über ein Web-Panel (`http://127.0.0.1:8088`) oder `config.yaml`, nicht über Hardcoding im Python-Code.

---

## 📦 2. Technologie-Stack & Bibliotheken

| Bereich | Empfohlene Bibliothek / Werkzeug | Begründung |
| :--- | :--- | :--- |
| **Sprache** | Python 3.10+ | Breites KI- und OS-Ökosystem |
| **Wake Word** | `openWakeWord` + `onnxruntime` | Open-Source, < 1 % CPU-Last, vortrainiertes Modell für `"computer"` |
| **Audio I/O & VAD** | `sounddevice`, `numpy`, `scipy` | Reine Wheel-Installation ohne `pyaudio` C++-Build-Probleme unter Windows |
| **Screen Capture** | `mss`, `Pillow` | Ultraschnell (~5–10 ms pro Frame), plattformübergreifend, Multi-Monitor-fähig |
| **Brain / Inferenz** | `transformers` / `accelerate` / `torch` (Liquid LFM3-Omni-2B) | Lokale Ausführung mit CUDA / DirectML / CPU Fallback |
| **Aktionen / OS** | `pyautogui`, `pynput`, `pywinctl`, `webbrowser` | Maus, Tastatur, native Fenster-Handles (`pywinctl`) & Media-Keys |
| **Control Panel** | `fastapi`, `uvicorn`, `pystray` | Leichtgewichtiges System-Tray + lokales Web-Dashboard |
| **Konfiguration** | `pydantic`, `pyyaml` | Typisierte und validierte Einstellungen |

---

## 🔄 3. Datenfluss & Schnittstellen-Verträge

### Ablauf eines Sprachbefehls:
```
1. Trigger-Event:
   openWakeWord erkennt "Computer" im laufenden Ring-Buffer (oder PTT gedrückt)
        │
        ├──> Akustisches Feedback: Kurzer LCARS-Chirp (< 50 ms)
        │
        ├─────────────────────────────────────────┐
        ▼                                         ▼
   Audio-Recorder übernimmt                  Screen-Capture schießt Snapshot
   Nahtlos ab Ende des Wake-Words            (standardmäßig bei `on_speech_end`,
   aus dem Ring-Buffer bis VAD               damit Zeigegesten der Maus wie
   Stille meldet (z. B. 1.2s)                "klicke hier" aktuell sind)
        │                                         │
        └────────────────────┬────────────────────┘
                             │
                             ▼
2. Brain-Anfrage:
   LFM3-Omni-2B empfängt:
   - System Prompt + JSON Schema + Aktuelle Cursor-Position (x_norm, y_norm)
   - Audio-Puffer (16kHz Mono WAV / PCM)
   - Bild-Puffer (Reskaliertes RGB Image + optionales Set-of-Marks Overlay)
                             │
                             ▼
3. Brain-Antwort (Strukturiertes JSON mit Action-Chaining):
   {
     "intent": "search_on_youtube",
     "spoken_response": "Suche nach Star Trek.",
     "requires_confirmation": false,
     "actions": [
       {
         "type": "click",
         "target": "YouTube Search Input",
         "x_norm": 450,
         "y_norm": 72,
         "button": "left"
       },
       {
         "type": "type_text",
         "text": "Star Trek TNG",
         "press_enter": true
       }
     ]
   }
                             │
                             ▼
4. Actuator-Ausführung:
   - Prüft Sicherheitsrichtlinie (`safe_mode` & `requires_confirmation`)
   - Transformiert `x_norm, y_norm` (0..1000) -> echte Monitor-Koordinaten `(x, y)`
   - Führt Aktionskette sequenziell aus
   - Loggt Befehl, Snapshot & Klick-Koordinaten für das Control Panel
```

---

## 🛠️ 4. Modul-Spezifikationen

### A. `computerflow/audio/`
* `wake_word.py` & `recorder.py`:
  * Nutzt **einen gemeinsamen** `sounddevice.InputStream` (16 kHz, Mono, `int16`), der kontinuierlich in einen `collections.deque`-Ringbuffer schreibt.
  * Sobald `openWakeWord` für `"computer"` über `wake_word_sensitivity` ausschlägt (oder PTT gedrückt wird), wechselt die State-Machine auf `RECORDING`, behält den relevanten Pre-Roll aus dem Ringbuffer und nimmt auf, bis die Energie-/VAD-Erkennung für `vad_silence_duration_seconds` Stille meldet.
* `feedback.py`:
  * Synthetisiert per `numpy`/`scipy` latenzfreie, subtile Sci-Fi-Bestätigungstöne (Wake-Chirp, Action-Success, Error-Buzz) ohne externe Audio-Assets zwingend vorauszusetzen.

### B. `computerflow/vision/`
* `screen_capture.py`:
  * Aktiviert beim Initialisieren unter Windows High-DPI Awareness (`SetProcessDpiAwareness(2)`), damit `mss` und `pyautogui` identische physische Pixel verwenden.
  * Ermittelt bei `monitor_mode: "active_cursor"` über `pyautogui.position()` automatisch den Monitor, auf dem sich der Mauszeiger gerade befindet.
  * Gibt ein `SnapshotContext`-Objekt zurück:
    * `image`: Das auf `max_resolution` skalierte `PIL.Image`
    * `monitor_bounds`: `{"left": int, "top": int, "width": int, "height": int}` des gecapturten Monitors
    * `cursor_norm`: `(x_norm, y_norm)` der aktuellen Mausposition im Bereich `0..1000`
  * Bietet die Hilfsmethode `norm_to_screen(x_norm: int, y_norm: int, monitor_bounds: dict) -> tuple[int, int]`, um Modell-Ausgaben exakt in OS-Mauskoordinaten umzurechnen.
* `som_overlay.py`:
  * Optionales Modul, das klickbare Regionen oder ein feines Koordinaten-/Badge-Grid einzeichnet, um kleinen Modellen (2B) präzises visuelles Grounding zu ermöglichen.

### C. `computerflow/brain/`
* `actions_schema.py`:
  * Definiert mittels `pydantic` die erlaubten Action-Typen:
    * `click` (`x_norm`, `y_norm`, `button`, `double`, `element_id`)
    * `move_to` (`x_norm`, `y_norm`)
    * `scroll` (`dx`, `dy`)
    * `type_text` (`text`, `press_enter`)
    * `hotkey` (`keys`: `list[str]`)
    * `focus_window` (`title_query`: `str`)
    * `media_control` (`command`: `"play_pause" | "next" | "prev" | "volume_up" | "volume_down" | "mute"`)
    * `open_url` (`url`: `str`)
    * `launch_app` (`app_name`: `str`)
* `lfm_client.py`:
  * Kapselt die Inferenz des LFM3-Omni-2B Modells (CUDA / DirectML / CPU) inkl. sauberem Mock-/Stub-Modus für Tests ohne geladene Modellgewichte.

### D. `computerflow/actuator/`
* `executor.py`:
  * Iteriert über die `actions`-Liste einer `BrainResponse`.
  * Blockiert nicht-freigegebene Aktionen (gemäß `config.actuator`) oder fordert bei `requires_confirmation: true` / `safe_mode` Bestätigung an.
  * Nutzt `os_actions.py` (`pywinctl` für schnellen Fensterwechsel, `pyautogui` Media-Keys) und `ui_actions.py` (normalisierte Mausklicks und Tastatureingaben).

### E. `computerflow/panel/`
* Lokales Web-Dashboard unter `http://127.0.0.1:8088` (FastAPI).
* Zeigt Status, letzte Befehle, erkannte Aktionen, den letzten Snapshot inkl. eingezeichnetem Ziel-Klickpunkt und erlaubt das Bearbeiten der `config.yaml` in Echtzeit.
* System-Tray-Icon (`pystray`), um den Assistenten zu pausieren, einen manuellen Trigger auszulösen oder das Dashboard zu öffnen.

---

## 📋 5. Konkreter Arbeitsauftrag für den nächsten Agenten

Wenn du als Agent dieses Projekt implementierst, halte dich an folgende Reihenfolge:

1. **Schritt 1: Grundgerüst & Konfiguration (`computerflow/core/`)**
   * Erstelle die Paketstruktur unter `computerflow/`.
   * Implementiere `config_manager.py` mit `pydantic` passend zur erweiterten `config.example.yaml` sowie `state.py` (Event-Bus & Command-History).
2. **Schritt 2: Screen-Capture & Koordinaten-Transformation (`computerflow/vision/`)**
   * Implementiere `screen_capture.py` inkl. Windows High-DPI Fix, `active_cursor`-Monitorerkennung und `norm_to_screen()` Umrechnung (`0..1000` -> echte Monitor-Koordinaten).
   * Implementiere `som_overlay.py` für optionales visuelles Grounding.
3. **Schritt 3: Audio-Ringbuffer, Trigger & Feedback (`computerflow/audio/`)**
   * Implementiere `feedback.py` (synthetische LCARS-Chirp-Töne), `recorder.py` (Rolling Ring-Buffer + VAD), `wake_word.py` (`openWakeWord` über `sounddevice`) und `push_to_talk.py`.
4. **Schritt 4: Action-Schema & Brain-Client (`computerflow/brain/`)**
   * Implementiere `actions_schema.py` (unterstützt Action-Chaining und `0..1000` Koordinaten), `prompt_templates.py` und `lfm_client.py` (mit echtem Model-Loader + intelligentem Mock-Fallback).
5. **Schritt 5: Actuator & Native OS-Reflexe (`computerflow/actuator/`)**
   * Implementiere `os_actions.py` (`pywinctl` Fensterfokus, Media-Keys, URLs), `ui_actions.py` und `executor.py`.
6. **Schritt 6: Settings-Panel, Tray-Icon & Tests (`computerflow/panel/`, `tests/`)**
   * Implementiere das FastAPI-Dashboard (`server.py`, `web/`), `tray.py`, `main.py` sowie Unit-Tests für Config, Koordinaten-Mapping und Action-Execution.
