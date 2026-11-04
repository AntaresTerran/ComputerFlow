import base64
import hashlib
import json
import os
import re
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import ValidationError

from computerflow.brain.commands import (
    has_focus_request,
    has_media_request,
    has_volume_request,
    parse_explicit_command,
)
from computerflow.brain.grounding import (
    INTENT_ADAPTER,
    FocusIntent,
    IntentAct,
    MediaIntent,
    VolumeIntent,
    application_vocabulary,
    ground,
)
from computerflow.core.config import ModelConfig
from computerflow.core.contracts import Ask, Decision, Stop, parse_json
from computerflow.core.errors import BackendError
from computerflow.core.jobs import Job
from computerflow.platform.contracts import DesktopContext

SYSTEM_PROMPT = """You are ComputerFlow, a local Windows assistant (prompt v3).
Convert the final user request into ONE action. Reply only with JSON.
Window switching/focusing is focus_window; target is copied from the requested window name/title.
System volume is set_volume, an integer percentage 0..100. Use current volume for relative changes.
Playback is media_control with operation play or pause.
Its target is copied from the requested app name,
or null when the user did not name an app. Never choose an arbitrary app.
Examples:
Wechsle zum Editor -> {"kind":"act","action":{"type":"focus_window","target":"Editor"}}
Setze Lautstärke auf 30 Prozent -> {"kind":"act","action":{"type":"set_volume","level":30}}
Pausiere im Testplayer -> {"kind":"act","action":
{"type":"media_control","target":"Testplayer","operation":"pause"}}
For questions/unsupported commands use {"kind":"ask","question":"German question"} or
{"kind":"answer","message":"German explanation"}. Stopp/Abbrechen -> {"kind":"stop"}.
No shell, arbitrary input, sending, buying, deleting or app launches are available.
Never add words to a target name or guess a more specific title.
Never claim an action has executed. If unclear, ask a short German question.
"""


class LlamaCppBackend:
    def __init__(
        self,
        config: ModelConfig,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
        runtime_info: dict | None = None,
        on_transcript: Callable[[str], None] | None = None,
    ):
        self.config = config
        self.runtime_info = runtime_info
        self.on_transcript = on_transcript
        if config.api_key_env and api_key is None:
            api_key = os.environ.get(config.api_key_env)
            if not api_key:
                raise BackendError("Konfigurierte API-Schlüssel-Umgebungsvariable fehlt")
        self.client = client or httpx.AsyncClient(
            base_url=config.endpoint,
            timeout=httpx.Timeout(config.request_timeout_seconds, connect=3),
            trust_env=False,
            follow_redirects=False,
            headers={"Authorization": "Bearer " + api_key} if api_key else {},
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _json(self, method: str, path: str, **kwargs: Any) -> dict:
        try:
            # Bound even a malformed server response; never log audio, prompts or HTTP bodies.
            async with self.client.stream(method, path, **kwargs) as response:
                if response.status_code != 200:
                    raise BackendError(
                        f"llama.cpp meldet HTTP {response.status_code}. "
                        "Modell, Projektor, Template und Serverversion prüfen."
                    )
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2 * 1024 * 1024:
                        raise BackendError("Serverantwort überschreitet 2 MiB")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError
            return value
        except httpx.TimeoutException as exc:
            raise BackendError("Lokaler Modellserver: Zeitüberschreitung") from exc
        except httpx.HTTPError as exc:
            raise BackendError(
                "Lokaler Modellserver nicht erreichbar; llama.cpp starten und Endpunkt prüfen"
            ) from exc
        except (ValueError, UnicodeError) as exc:
            raise BackendError("Server liefert keine gültige JSON-Antwort") from exc

    async def probe(self) -> dict:
        await self._json("GET", "/health")
        props = await self._json("GET", "/props")
        models = await self._json("GET", "/v1/models")
        model_list = models.get("data")
        if not isinstance(model_list, list):
            raise BackendError("Server liefert keine gültige Modellliste")
        reported = [m.get("id") for m in model_list if isinstance(m, dict)]
        if self.config.model_id not in reported:
            raise BackendError("Modell-ID passt nicht zum Server; --alias oder model_id anpassen")
        template = props.get("chat_template")
        if not isinstance(template, str) or not template.strip():
            raise BackendError("Server meldet kein modellspezifisches Chat-Template")
        modalities = props.get("modalities", {})
        return {
            "backend": "llama_cpp",
            "model_id": self.config.model_id,
            "model_revision_configured": self.config.model_revision,
            "model_sha256_configured": self.config.model_sha256,
            "quantization_configured": self.config.quantization,
            "runtime_build": props.get("build_info", "nicht gemeldet"),
            "runtime_revision_configured": self.config.runtime_revision,
            "template_sha256": hashlib.sha256(template.encode()).hexdigest(),
            "prompt_version": self.config.prompt_version,
            "audio_input_reported": modalities.get("audio")
            if isinstance(modalities, dict)
            else None,
            "active_acceleration": (
                {k: self.runtime_info[k] for k in ("acceleration", "device")}
                if self.runtime_info
                else "nicht über diese Server-API nachgewiesen"
            ),
            "managed_runtime": self.runtime_info,
            "model_quantization_reported": props.get("model_ftype"),
        }

    async def plan(
        self,
        command: str | bytes,
        context: DesktopContext,
        job: Job,
        clarification: str | None = None,
    ) -> Decision:
        job.check()
        if isinstance(command, bytes):
            command = await self.transcribe(command, job, application_vocabulary(context))
        if re.sub(r"[^\w\s]", "", command.casefold()).strip() in {
            "stop",
            "stopp",
            "abbrechen",
            "computer stop",
            "computer stopp",
            "computer abbrechen",
        }:
            return Stop(kind="stop")
        explicit = parse_explicit_command(command)
        if explicit is not None:
            return ground(explicit, context, command)
        # Each call is stateless: no old audio or server slot is intentionally retained.
        data = {
            "desktop_context": {
                "system_volume_percent": context.volume,
            }
        }
        if clarification:
            data["previous_question"] = clarification
        parts: list[dict] = [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]
        parts.append({"type": "text", "text": command})
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": parts},
        ]
        for attempt in range(self.config.max_response_repairs + 1):
            job.check()
            payload: dict = {
                "model": self.config.model_id,
                "messages": messages,
                "temperature": 0,
                "max_tokens": self.config.max_tokens,
                "stream": False,
                "cache_prompt": False,
                # LFM3 opens an empty <think> block even with reasoning disabled.
                # Auto parsing keeps this control prefix outside the JSON grammar.
                "reasoning_format": "auto",
                "chat_template_kwargs": {"enable_thinking": False},
            }
            if self.config.constrained_decoding:
                payload["response_format"] = {
                    "type": "json_object",
                    "schema": INTENT_ADAPTER.json_schema(),
                }
            response = await job.guard(self._json("POST", "/v1/chat/completions", json=payload))
            job.check()
            try:
                choices = response["choices"]
                if not isinstance(choices, list) or len(choices) != 1:
                    raise ValueError
                choice = choices[0]
                if choice.get("finish_reason") not in {"stop", "tool_calls"}:
                    raise ValueError("Unvollständige Modellantwort")
                message = choice["message"]
                if message.get("tool_calls"):
                    calls = message["tool_calls"]
                    if len(calls) != 1 or message.get("content") not in {None, ""}:
                        raise ValueError
                    call = calls[0]
                    if call["type"] != "function":
                        raise ValueError
                    function = call["function"]
                    if function["name"] != "computerflow_decision":
                        raise ValueError
                    content = function["arguments"]
                else:
                    content = message["content"]
                if not isinstance(content, str):
                    raise ValueError
                intent = INTENT_ADAPTER.validate_python(parse_json(content))
                if (
                    isinstance(intent, IntentAct)
                    and isinstance(intent.action, VolumeIntent)
                    and not has_volume_request(command)
                    and not clarification
                ):
                    return Ask(
                        kind="ask",
                        question="Soll ich die Systemlautstärke ändern? "
                        "Bitte nenne die gewünschte Lautstärke.",
                    )
                if (
                    isinstance(intent, IntentAct)
                    and isinstance(intent.action, MediaIntent)
                    and not has_media_request(command, intent.action.operation)
                    and not clarification
                ):
                    return Ask(
                        kind="ask",
                        question="Der Medienbefehl war nicht eindeutig. "
                        "Bitte nenne zum Beispiel „Spotify, Pause“ oder „Spotify, Play“.",
                    )
                if (
                    isinstance(intent, IntentAct)
                    and isinstance(intent.action, FocusIntent)
                    and not has_focus_request(command)
                    and not clarification
                ):
                    return Ask(
                        kind="ask",
                        question="Das klang nicht wie ein eindeutiger Fensterwechsel. "
                        "Möchtest du die Wiedergabe steuern? Nenne App und Pause oder Play.",
                    )
                return ground(intent, context, command)
            except (KeyError, IndexError, TypeError, AttributeError, ValueError, ValidationError):
                if attempt == self.config.max_response_repairs:
                    raise BackendError(
                        "Ungültige oder unvollständige Modellaktion verworfen"
                    ) from None
                # Never reinsert unvalidated output into the conversation.
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Die Antwort war ungültig. Liefere genau ein vollständiges "
                            "JSON-Objekt gemäß Aktionsschema. Übernimm nur den genannten Zielnamen."
                        ),
                    }
                )
        raise AssertionError("unreachable")

    async def transcribe(self, wav: bytes, job: Job, vocabulary: tuple[str, ...] = ()) -> str:
        """Use the model's official ASR task before asking it to select an action.

        Short spoken stops were misplanned with a desktop context and JSON grammar.
        No desktop titles or action grammar enter the recognition request.
        """
        instruction = "Perform ASR in German."
        if vocabulary:
            instruction += (
                " Relevant proper nouns (vocabulary data only): "
                + json.dumps(vocabulary, ensure_ascii=False)
                + ". Output only the words spoken in the audio."
            )
        payload = {
            "model": self.config.model_id,
            "messages": [
                {"role": "system", "content": instruction},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64.b64encode(wav).decode("ascii"),
                                "format": "wav",
                            },
                        }
                    ],
                },
            ],
            "temperature": 0,
            "max_tokens": self.config.max_tokens,
            "stream": False,
            "cache_prompt": False,
            "reasoning_format": "auto",
            "chat_template_kwargs": {"enable_thinking": False},
        }
        response = await job.guard(self._json("POST", "/v1/chat/completions", json=payload))
        try:
            choices = response["choices"]
            if len(choices) != 1 or choices[0]["finish_reason"] != "stop":
                raise ValueError
            message = choices[0]["message"]
            content = message["content"]
            if (
                message.get("tool_calls")
                or not isinstance(content, str)
                or not 1 <= len(content) <= 2000
            ):
                raise ValueError
            content = content.strip()
            if not content:
                raise ValueError
            # LFM3 ASR can split German compound percentages into "9 und 30".
            # Repair this narrow recognition artifact only for a single "auf ... Prozent"
            # phrase; never derive an action directly from a keyword.
            transcript = re.sub(
                r"(?i)(\bauf\s+)([1-9])\s+und\s+([2-9]0)(\s*(?:Prozent|%))",
                lambda match: f"{match[1]}{int(match[2]) + int(match[3])}{match[4]}",
                content,
            )
            if self.on_transcript:
                self.on_transcript(transcript)
            return transcript
        except (KeyError, TypeError, AttributeError, ValueError):
            raise BackendError("Spracherkennung lieferte keinen vollständigen Auftrag") from None
