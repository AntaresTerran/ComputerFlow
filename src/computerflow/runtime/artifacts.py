import hashlib
import os
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from computerflow.core.errors import ComputerFlowError

REVISION = "d508b88f08a5b4286f2d2805a6a8d69a0ff44c72"
BUILD = "b11960"
BUILD_COMMIT = "8642541b255bfb5dc39cd351a178be09013a55d6"
REPOSITORY = "LiquidAI/LFM3-Omni-2B-GGUF"


@dataclass(frozen=True)
class Artifact:
    name: str
    url: str
    sha256: str
    size: int


MODEL = Artifact(
    "LFM3-Omni-2B-Q4_K_M.gguf",
    f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/LFM3-Omni-2B-Q4_K_M.gguf",
    "9f8d30e9d4fd7a9349d586e077988229b3ca0a0e4ad730897563d1eccc9893e2",
    1099630080,
)
PROJECTOR = Artifact(
    "mmproj-LFM3-Omni-2B-Q8_0.gguf",
    f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/mmproj-LFM3-Omni-2B-Q8_0.gguf",
    "8a25f9d1931244429de404fccacfb7fb933970a36aa5688d2f5069f29c6b27b1",
    506842528,
)
WAKE_MODEL = Artifact(
    "vosk-model-small-de-0.15.zip",
    "https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip",
    "b7e53c90b1f0a38456f4cd62b366ecd58803cd97cd42b06438e2c131713d5e43",
    46499967,
)
SPEAKER_MODEL = Artifact(
    "vosk-model-spk-0.4.zip",
    "https://alphacephei.com/vosk/models/vosk-model-spk-0.4.zip",
    "a74d8f51144484813e16af689bb0f916b7a111e2347f467c4933c1166097b5a7",
    13869103,
)
MODEL_LICENSE = Artifact(
    "LICENSE",
    f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/LICENSE",
    "4d28ca14dedc0b3d0fcc2b3339f0e79931faa33874f3d24f522183a8fc70068c",
    10574,
)
MODEL_CARD = Artifact(
    "README.md",
    f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/README.md",
    "fe6124bbfd92bf0a5775e7e157ce59065519f179966dfff35f51170f83ca9339",
    7085,
)


def runtime_artifact(acceleration: str) -> Artifact:
    name = f"llama-{BUILD}-bin-win-{acceleration}-x64.zip"
    metadata = {
        "vulkan": ("bac6914b5e83523eb008c6789eaa12669f93fbc196c3b9e8237b6672323b33e9", 37345851),
        "cpu": ("73f962f82850d244db47eaacb9d913637027b82399124324298576d58c5f4287", 24407745),
    }
    digest, size = metadata[acceleration]
    return Artifact(
        name,
        f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD}/{name}",
        digest,
        size,
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(
    artifact: Artifact,
    directory: Path,
    progress: Callable[[str], None] = print,
    client: httpx.Client | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / artifact.name
    if target.exists():
        if target.stat().st_size == artifact.size and file_sha256(target) == artifact.sha256:
            progress(f"Geprüft: {artifact.name}")
            return target
        raise ComputerFlowError(
            f"Prüfsumme falsch: {target}; Datei vor Neuinstallation verschieben"
        )
    partial = target.with_suffix(target.suffix + ".part")
    start = partial.stat().st_size if partial.exists() else 0
    if start > artifact.size:
        raise ComputerFlowError(f"Unpassender Teildownload: {partial}")
    progress(f"Download {artifact.name}: {artifact.size / 1024**2:.1f} MiB")
    owned = client is None
    client = client or httpx.Client(
        timeout=httpx.Timeout(60, connect=15),
        follow_redirects=True,
        trust_env=False,
    )
    try:
        if start != artifact.size:
            with client.stream(
                "GET", artifact.url, headers={"Range": f"bytes={start}-"}
            ) as response:
                if response.status_code not in {200, 206}:
                    raise ComputerFlowError(f"Download fehlgeschlagen: HTTP {response.status_code}")
                if response.status_code == 206:
                    expected = f"bytes {start}-"
                    if not response.headers.get("content-range", "").startswith(expected):
                        raise ComputerFlowError("Unpassender Content-Range beim Fortsetzen")
                else:
                    start = 0
                received = start
                reported = -1
                with partial.open("ab" if start else "wb") as stream:
                    for chunk in response.iter_bytes(1024 * 1024):
                        received += len(chunk)
                        if received > artifact.size:
                            raise ComputerFlowError("Download ist größer als die festgelegte Datei")
                        stream.write(chunk)
                        percent = int(received / artifact.size * 100)
                        if percent // 5 != reported:
                            progress(f"{artifact.name}: {percent} %")
                            reported = percent // 5
        if partial.stat().st_size != artifact.size or file_sha256(partial) != artifact.sha256:
            partial.unlink(missing_ok=True)
            raise ComputerFlowError(
                f"Integritätsprüfung fehlgeschlagen: {artifact.name}; setup erneut starten"
            )
        os.replace(partial, target)
        progress(f"SHA-256 bestätigt: {artifact.name}")
        return target
    except httpx.HTTPError as exc:
        raise ComputerFlowError(
            "Download unterbrochen; setup erneut starten, um den Teildownload fortzusetzen"
        ) from exc
    finally:
        if owned:
            client.close()


def extract_verified_zip(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            path = (root / info.filename).resolve()
            if not path.is_relative_to(root) or info.file_size > 512 * 1024**2:
                raise ComputerFlowError("Unzulässiger Pfad/Dateigröße im Laufzeitarchiv")
        for info in source.infolist():
            path = root / info.filename
            if info.is_dir():
                path.mkdir(parents=True, exist_ok=True)
                continue
            expected = hashlib.sha256(source.read(info)).hexdigest()
            if path.is_file() and file_sha256(path) == expected:
                continue  # Safe to rerun setup while the unchanged executable is in use.
            temporary = path.with_name(path.name + ".extracting")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(source.read(info))
            os.replace(temporary, path)


def extract_runtime(archive: Path, target: Path) -> Path:
    extract_verified_zip(archive, target)
    root = target.resolve()
    matches = list(root.rglob("llama-server.exe"))
    if len(matches) != 1:
        raise ComputerFlowError("Laufzeitarchiv enthält keinen eindeutigen llama-server.exe")
    return matches[0]
