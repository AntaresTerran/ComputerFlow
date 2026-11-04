import json
import os
import platform
import re
import secrets
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import psutil

from computerflow.core.config import Config, program_root, save_config
from computerflow.core.errors import ComputerFlowError
from computerflow.platform.protection import protect, unprotect
from computerflow.runtime.artifacts import (
    BUILD,
    BUILD_COMMIT,
    MODEL,
    MODEL_CARD,
    MODEL_LICENSE,
    PROJECTOR,
    REPOSITORY,
    REVISION,
    download,
    extract_runtime,
    file_sha256,
    runtime_artifact,
)


def runtime_root(config: Config) -> Path:
    root = program_root()
    return (root / (config.runtime.data_dir or ".computerflow")).resolve()


def read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (OSError, ValueError) as exc:
        raise ComputerFlowError(f"Ungültige lokale Laufzeitdatei: {path.name}") from exc


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


@contextmanager
def lifecycle_lock(root: Path):
    """Serialize starts/stops across CLIs without ever targeting a foreign process."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / "lifecycle.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if sys.platform == "win32":
            import msvcrt

            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ComputerFlowError("Serververwaltung ist bereits aktiv; kurz warten") from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ComputerFlowError("Serververwaltung ist bereits aktiv; kurz warten") from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def save_setup(config: Config, profile: dict, path: Path | None = None) -> Path:
    data = config.model_dump(mode="json")
    data["model"].update(
        {
            "model_revision": profile["model_revision"],
            "runtime_revision": profile["build"],
            "model_sha256": profile["model_sha256"],
            "quantization": profile["quantization"],
        }
    )
    return save_config(Config.model_validate(data), path)


def clean_environment() -> dict[str, str]:
    # Environment settings must not enable llama.cpp tools, networking or prompt logging.
    return {k: v for k, v in os.environ.items() if not k.startswith(("LLAMA_", "GGML_"))}


def detect_devices(executable: Path) -> list[dict]:
    try:
        result = subprocess.run(
            [str(executable), "--list-devices"],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=clean_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode:
        return []
    return parse_devices(result.stdout + result.stderr)


def parse_devices(output: str) -> list[dict]:
    result = []
    for match in re.finditer(
        r"^\s*(Vulkan\d+): (.+?) \((\d+) MiB, (\d+) MiB free\)",
        output,
        re.MULTILINE,
    ):
        result.append(
            {
                "id": match[1],
                "name": match[2],
                "memory_mib": int(match[3]),
                "free_mib": int(match[4]),
            }
        )
    return result


def install(config: Config, progress: Callable[[str], None] = print) -> dict:
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ComputerFlowError("Verwaltete Laufzeit unterstützt Windows x64")
    root = runtime_root(config)
    profile_path = root / "installation.json"
    model = download(MODEL, root / "models", progress)
    projector = download(PROJECTOR, root / "models", progress)
    executables = {}
    for kind in ("vulkan", "cpu"):
        archive = download(runtime_artifact(kind), root / "downloads", progress)
        executables[kind] = extract_runtime(archive, root / "runtime" / BUILD / kind)
    devices = detect_devices(executables["vulkan"])
    candidates = [d for d in devices if d["free_mib"] >= 4096]
    if config.runtime.device:
        candidates = [d for d in candidates if d["id"] == config.runtime.device]
    use_gpu = config.runtime.acceleration != "cpu" and bool(candidates)
    if config.runtime.acceleration == "vulkan" and not use_gpu:
        raise ComputerFlowError(
            "Gewünschtes Vulkan-Gerät ist nicht mit ausreichend Speicher verfügbar"
        )
    selected = candidates[0] if use_gpu else None
    acceleration = "vulkan" if use_gpu else "cpu"
    profile = {
        "schema_version": 1,
        "build": BUILD,
        "build_commit": BUILD_COMMIT,
        "repository": REPOSITORY,
        "model_revision": REVISION,
        "model_path": str(model.resolve().relative_to(root)),
        "model_sha256": MODEL.sha256,
        "projector_path": str(projector.resolve().relative_to(root)),
        "projector_sha256": PROJECTOR.sha256,
        "quantization": "Q4_K_M",
        "projector_quantization": "Q8_0",
        "executables": {k: str(p.relative_to(root)) for k, p in executables.items()},
        "executable_sha256": {k: file_sha256(p) for k, p in executables.items()},
        "devices": devices,
        "device": selected,
        "acceleration": acceleration,
    }
    # These pinned text artifacts are cached too; repeated setup works offline.
    for artifact in (MODEL_LICENSE, MODEL_CARD):
        download(artifact, root / "models", progress)
    write_json(profile_path, profile)
    progress(
        f"Eingerichtet: {BUILD}, Q4_K_M + Projektor Q8_0, "
        + (f"Vulkan / {selected['name']}" if selected else "CPU-Fallback (sichtbar)")
    )
    return profile


def verified_process(state: dict | None) -> psutil.Process | None:
    if not state:
        return None
    try:
        process = psutil.Process(state["pid"])
        if (
            abs(process.create_time() - state["created_at"]) > 0.01
            or Path(process.exe()).resolve() != Path(state["executable"]).resolve()
        ):
            return None
        return process
    except (KeyError, TypeError, ValueError, psutil.Error, OSError):
        return None


class ManagedRuntime:
    def __init__(self, config: Config, status: Callable[[str], None] = print):
        self.config = config
        self.status = status
        self.root = runtime_root(config)
        self.state_path = self.root / "server-state.tmp"

    def _installed_path(self, value: str) -> Path:
        path = (self.root / value).resolve()
        if not path.is_relative_to(self.root):
            raise ComputerFlowError("Installationspfad liegt außerhalb des ComputerFlow-Ordners")
        return path

    def connection(self) -> dict | None:
        state = read_json(self.state_path)
        if (
            state
            and state.get("endpoint") == self.config.model.endpoint
            and verified_process(state)
        ):
            required = {
                "protected_key",
                "acceleration",
                "device",
                "build",
                "model_revision",
                "model_sha256",
                "projector_sha256",
                "quantization",
            }
            if not required.issubset(state) or not isinstance(state["protected_key"], str):
                raise ComputerFlowError(
                    "Serverzustand unvollständig; server stop und start ausführen"
                )
            try:
                state["api_key"] = unprotect(state["protected_key"]).decode("ascii")
            except (OSError, ValueError) as exc:
                raise ComputerFlowError("Server-Schlüssel kann nicht lokal gelesen werden") from exc
            return state
        return None

    def start(self) -> dict:
        with lifecycle_lock(self.root):
            return self._start()

    def _start(self) -> dict:
        if sys.platform != "win32":
            raise ComputerFlowError("Verwalteter Server ist nur auf Windows verfügbar")
        running = self.connection()
        if running:
            if (
                self.config.runtime.acceleration not in {"auto", running["acceleration"]}
                or self.config.runtime.device
                and self.config.runtime.device != ((running.get("device") or {}).get("id"))
            ):
                raise ComputerFlowError("Hardwarewahl geändert; zuerst computerflow server stop")
            self._wait_ready(running)
            self.status(f"Modellserver bereit: {running['endpoint']} ({running['acceleration']})")
            return running
        old = read_json(self.state_path)
        if verified_process(old):
            raise ComputerFlowError(
                "Ein verwalteter Server läuft auf anderem Port; zuerst server stop"
            )
        endpoint = urlsplit(self.config.model.endpoint)
        host, port = endpoint.hostname, endpoint.port or 80
        family = socket.AF_INET6 if host == "::1" else socket.AF_INET
        with socket.socket(family) as check:
            try:
                check.bind((host, port))
            except OSError as exc:
                raise ComputerFlowError(
                    f"Port {port} ist belegt oder reserviert; model.endpoint ändern. "
                    "Ein fremder Prozess wird nicht beendet."
                ) from exc
        profile = read_json(self.root / "installation.json")
        if not profile:
            profile = install(self.config, self.status)
        if self.config.model.model_id != REPOSITORY:
            raise ComputerFlowError("Anderes Modell erfordert runtime.managed: false")
        device = profile["device"]
        if self.config.runtime.device:
            device = next(
                (d for d in profile["devices"] if d["id"] == self.config.runtime.device),
                None,
            )
        kind = profile["acceleration"]
        if self.config.runtime.acceleration != "auto":
            kind = self.config.runtime.acceleration
        if kind == "vulkan" and device is None:
            raise ComputerFlowError("Kein passendes Vulkan-Gerät; setup erneut ausführen")
        attempts = (
            [kind, "cpu"]
            if kind == "vulkan" and self.config.runtime.acceleration == "auto"
            else [kind]
        )
        for kind in attempts:
            executable = self._installed_path(profile["executables"][kind])
            if file_sha256(executable) != profile["executable_sha256"][kind]:
                raise ComputerFlowError(
                    "Serverdatei verändert; computerflow setup erneut ausführen"
                )
            for artifact, key in ((MODEL, "model_path"), (PROJECTOR, "projector_path")):
                path = self._installed_path(profile[key])
                if path.stat().st_size != artifact.size or file_sha256(path) != artifact.sha256:
                    raise ComputerFlowError("Modell/Projektor verändert; setup erneut ausführen")
            key = secrets.token_urlsafe(32)
            protected_key = protect(key.encode("ascii"))
            env = clean_environment()
            env["LLAMA_API_KEY"] = key
            args = [
                str(executable),
                "--model",
                str(self._installed_path(profile["model_path"])),
                "--mmproj",
                str(self._installed_path(profile["projector_path"])),
                "--host",
                host,
                "--port",
                str(port),
                "--alias",
                self.config.model.model_id,
                "--ctx-size",
                "8192",
                "--parallel",
                "1",
                "--threads",
                str(max(1, min(16, (os.cpu_count() or 2) // 2))),
                "--temp",
                "0",
                "--reasoning",
                "off",
                "--jinja",
                "--offline",
                "--no-webui",
                "--no-agent",
                "--no-ui-mcp-proxy",
                "--log-disable",
                "--cors-origins",
                "http://127.0.0.1:0",
                "--no-cors-credentials",
                "--device",
                (device["id"] if kind == "vulkan" else "none"),
                "--gpu-layers",
                ("all" if kind == "vulkan" else "0"),
            ]
            if kind == "cpu":
                args.append("--no-mmproj-offload")
            self.status(f"Starte Modellserver auf {host}:{port}: {kind}")
            process = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=executable.parent,
                env=env,
                close_fds=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            state = {
                "pid": process.pid,
                "created_at": psutil.Process(process.pid).create_time(),
                "executable": str(executable),
                "endpoint": self.config.model.endpoint,
                "api_key": key,
                "acceleration": kind,
                "device": device if kind == "vulkan" else None,
                "build": profile["build"],
                "model_revision": profile["model_revision"],
                "model_sha256": profile["model_sha256"],
                "projector_sha256": profile["projector_sha256"],
                "quantization": "Q4_K_M",
            }
            try:
                write_json(
                    self.state_path,
                    {k: v for k, v in state.items() if k != "api_key"}
                    | {"protected_key": protected_key},
                )
            except OSError:
                process.terminate()
                raise
            try:
                self._wait_ready(state)
                self.status(f"Modellserver bereit: {state['endpoint']} ({kind})")
                return state
            except ComputerFlowError:
                self._stop()
                if kind == attempts[-1]:
                    raise
                self.status(
                    "Vulkan-Start fehlgeschlagen; starte ausdrücklich sichtbaren CPU-Fallback"
                )
        raise AssertionError("unreachable")

    def _wait_ready(self, state: dict) -> None:
        deadline = time.monotonic() + self.config.runtime.startup_timeout_seconds
        with httpx.Client(
            base_url=state["endpoint"],
            timeout=2,
            trust_env=False,
            headers={"Authorization": "Bearer " + state["api_key"]},
        ) as client:
            while time.monotonic() < deadline:
                if not verified_process(state):
                    raise ComputerFlowError(
                        "Modellserver wurde beim Laden beendet; setup/Hardware prüfen"
                    )
                try:
                    health = client.get("/health")
                    if health.status_code == 200:
                        props = client.get("/props")
                        if props.status_code == 200 and props.json().get("modalities", {}).get(
                            "audio"
                        ):
                            return
                        if props.status_code in {401, 403}:
                            raise ComputerFlowError("Modellserver-Authentifizierung fehlgeschlagen")
                except httpx.HTTPError:
                    pass
                time.sleep(0.2)
        raise ComputerFlowError("Modellserver hat sein Startzeitlimit überschritten")

    def stop(self) -> bool:
        with lifecycle_lock(self.root):
            return self._stop()

    def _stop(self) -> bool:
        state = read_json(self.state_path)
        process = verified_process(state)
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except psutil.TimeoutExpired:
                # The exact same verified process object, never a new process by PID alone.
                process.kill()
                process.wait(timeout=5)
        self.state_path.unlink(missing_ok=True)
        return process is not None

    def public_status(self) -> dict:
        state = self.connection()
        if not state:
            return {"running": False, "endpoint": self.config.model.endpoint}
        return {
            k: state[k]
            for k in (
                "pid",
                "endpoint",
                "acceleration",
                "device",
                "build",
                "model_revision",
                "model_sha256",
                "projector_sha256",
                "quantization",
            )
        } | {
            "running": True,
        }
