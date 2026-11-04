import hashlib
import os
import zipfile
from pathlib import Path

import httpx
import pytest

from computerflow.core.config import Config, RuntimeConfig, load_config
from computerflow.core.errors import ComputerFlowError
from computerflow.runtime.artifacts import Artifact, download, extract_runtime
from computerflow.runtime.manager import (
    ManagedRuntime,
    clean_environment,
    lifecycle_lock,
    parse_devices,
    read_json,
    save_setup,
    verified_process,
    write_json,
)


def artifact(content=b"checked-test-binary"):
    return Artifact(
        "test.bin",
        "https://example.test/pinned/file",
        hashlib.sha256(content).hexdigest(),
        len(content),
    )


def test_download_is_verified_and_reused_without_network(tmp_path):
    value = b"checked-test-binary"
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, content=value)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        path = download(artifact(value), tmp_path, lambda _: None, client)
        assert path.read_bytes() == value
        assert download(artifact(value), tmp_path, lambda _: None, client) == path
    assert len(calls) == 1
    assert not path.with_suffix(".bin.part").exists()


def test_partial_download_resumes_with_a_checked_range(tmp_path):
    value = b"checked-test-binary"
    (tmp_path / "test.bin.part").write_bytes(value[:7])

    def respond(request):
        assert request.headers["Range"] == "bytes=7-"
        return httpx.Response(206, content=value[7:], headers={"Content-Range": "bytes 7-18/19"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = download(artifact(value), tmp_path, lambda _: None, client)
    assert result.read_bytes() == value


def test_server_ignoring_range_restarts_file(tmp_path):
    value = b"checked-test-binary"
    (tmp_path / "test.bin.part").write_bytes(value[:7])
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=value))
    ) as c:
        assert download(artifact(value), tmp_path, lambda _: None, c).read_bytes() == value


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"wrong-but-same-size"),
        httpx.Response(200, content=b"too long" * 40),
        httpx.Response(403),
        httpx.Response(206, content=b"x", headers={"Content-Range": "bytes 9-9/10"}),
    ],
)
def test_invalid_download_never_becomes_executable_or_final_file(tmp_path, response):
    with httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client:
        with pytest.raises(ComputerFlowError):
            download(artifact(), tmp_path, lambda _: None, client)
    assert not (tmp_path / "test.bin").exists()


def test_archive_cannot_write_outside_installation(tmp_path):
    path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("../escape.exe", b"bad")
        archive.writestr("llama-server.exe", b"bad")
    with pytest.raises(ComputerFlowError):
        extract_runtime(path, tmp_path / "runtime")
    assert not (tmp_path / "escape.exe").exists()


def test_unchanged_runtime_is_not_overwritten_while_server_may_be_running(tmp_path, monkeypatch):
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as source:
        source.writestr("llama-server.exe", b"checked")
    executable = extract_runtime(archive, tmp_path / "runtime")
    monkeypatch.setattr(zipfile.ZipFile, "extract", lambda *args: pytest.fail("unneeded overwrite"))
    assert extract_runtime(archive, tmp_path / "runtime") == executable


def test_gpu_start_failure_uses_visible_cpu_fallback(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import computerflow.runtime.manager as module

    cfg = Config(runtime=RuntimeConfig(data_dir=str(tmp_path)))
    runtime = ManagedRuntime(cfg, lambda _: None)
    data = b"test"
    digest = hashlib.sha256(data).hexdigest()
    for name in ("gpu.exe", "cpu.exe", "model.gguf", "projector.gguf"):
        (tmp_path / name).write_bytes(data)
    profile = {
        "acceleration": "vulkan",
        "device": {"id": "Vulkan0"},
        "devices": [],
        "executables": {"vulkan": str(tmp_path / "gpu.exe"), "cpu": str(tmp_path / "cpu.exe")},
        "executable_sha256": {"vulkan": digest, "cpu": digest},
        "model_path": str(tmp_path / "model.gguf"),
        "projector_path": str(tmp_path / "projector.gguf"),
        "model_sha256": digest,
        "projector_sha256": digest,
        "build": "pinned",
        "model_revision": "pinned",
    }
    write_json(tmp_path / "installation.json", profile)
    monkeypatch.setattr(module, "MODEL", artifact(data))
    monkeypatch.setattr(module, "protect", lambda _: "encrypted")
    monkeypatch.setattr(module, "PROJECTOR", artifact(data))
    monkeypatch.setattr(module.sys, "platform", "win32")
    monkeypatch.setattr(runtime, "connection", lambda: None)
    monkeypatch.setattr(runtime, "_stop", lambda: True)
    monkeypatch.setattr(
        module.psutil, "Process", lambda pid: SimpleNamespace(create_time=lambda: 1)
    )
    monkeypatch.setattr(module.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(module.subprocess, "CREATE_NEW_PROCESS_GROUP", 0, raising=False)

    class FreeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def bind(self, address):
            pass

    monkeypatch.setattr(module.socket, "socket", lambda *args: FreeSocket())
    launches, attempts = [], []

    def launch(args, **kwargs):
        launches.append((args, kwargs))
        assert kwargs["env"]["LLAMA_API_KEY"] not in args
        return SimpleNamespace(pid=100 + len(launches))

    def ready(state):
        attempts.append(state["acceleration"])
        if state["acceleration"] == "vulkan":
            raise ComputerFlowError("injected GPU failure")

    monkeypatch.setattr(module.subprocess, "Popen", launch)
    monkeypatch.setattr(runtime, "_wait_ready", ready)
    state = runtime._start()
    assert attempts == ["vulkan", "cpu"]
    assert state["acceleration"] == "cpu" and state["device"] is None
    assert "--no-mmproj-offload" in launches[1][0]


def test_gpu_probe_keeps_reported_order_not_integrated_shared_memory():
    devices = parse_devices(
        "Available devices:\n Vulkan0: Discrete GPU (24560 MiB, 23000 MiB free)\n"
        " Vulkan1: Integrated (78000 MiB, 75000 MiB free)\n"
    )
    assert devices[0]["name"] == "Discrete GPU"
    assert devices[1]["memory_mib"] == 78000


def test_inherited_runtime_environment_cannot_enable_agent_or_prompt_logging(monkeypatch):
    monkeypatch.setenv("LLAMA_ARG_TOOLS", "all")
    monkeypatch.setenv("LLAMA_ARG_LOG_FILE", "private-prompts.log")
    monkeypatch.setenv("GGML_RPC_SERVERS", "remote:123")
    env = clean_environment()
    assert "LLAMA_ARG_TOOLS" not in env
    assert "LLAMA_ARG_LOG_FILE" not in env
    assert "GGML_RPC_SERVERS" not in env
    assert env.get("PATH") == os.environ.get("PATH")


def test_foreign_or_reused_pid_is_never_stopped(tmp_path):
    config = Config(runtime=RuntimeConfig(data_dir=str(tmp_path)))
    import psutil

    own = psutil.Process()
    state = {
        "pid": own.pid,
        "created_at": own.create_time() - 1,
        "executable": own.exe(),
        "endpoint": config.model.endpoint,
        "api_key": "never-print",
    }
    write_json(ManagedRuntime(config).state_path, state)
    assert verified_process(state) is None
    assert ManagedRuntime(config).stop() is False
    assert own.is_running()


def test_occupied_port_does_not_start_or_kill_a_server(tmp_path, monkeypatch):
    config = Config(runtime=RuntimeConfig(data_dir=str(tmp_path)))
    runtime = ManagedRuntime(config)
    monkeypatch.setattr(runtime, "connection", lambda: None)
    monkeypatch.setattr("computerflow.runtime.manager.sys.platform", "win32")

    class BusySocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def bind(self, address):
            raise OSError("in use")

    monkeypatch.setattr("computerflow.runtime.manager.socket.socket", lambda *args: BusySocket())
    with pytest.raises(ComputerFlowError, match="belegt"):
        runtime._start()
    assert read_json(tmp_path / "server-state.json") is None


def test_lifecycle_operations_are_serialized(tmp_path):
    with lifecycle_lock(tmp_path):
        with pytest.raises(ComputerFlowError, match="bereits aktiv"):
            with lifecycle_lock(tmp_path):
                pytest.fail("second lifecycle operation acquired the same lock")


def test_setup_materializes_reusable_device_paths_and_revisions(tmp_path):
    config = Config(runtime=RuntimeConfig(data_dir=str(tmp_path / "data")))
    profile = {
        "model_revision": "revision",
        "build": "pinned-build",
        "model_sha256": "a" * 64,
        "quantization": "Q4_K_M",
    }
    path = save_setup(config, profile, tmp_path / "config.yaml")
    loaded = load_config(path)
    assert Path(loaded.runtime.data_dir).is_absolute()
    assert loaded.model.model_sha256 == "a" * 64
    assert loaded.model.runtime_revision == "pinned-build"
    assert "api_key:" not in path.read_text(encoding="utf-8")
