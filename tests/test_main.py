import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main


def test_build_gpu_install_command_for_cuda(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    monkeypatch.setenv("KAGGLE_KERNEL_RUN_TYPE", "Interactive")

    install_cmd, install_env = main.build_llama_cpp_install_command(cuda_arch="75")

    assert install_cmd[:4] == [sys.executable, "-m", "pip", "install"]
    assert "--extra-index-url" in install_cmd
    assert "https://abetlen.github.io/llama-cpp-python/whl/cu124" in install_cmd
    assert "llama-cpp-python" in install_cmd
    assert "-DGGML_CUDA=on" in install_env["CMAKE_ARGS"]
    assert "-DCMAKE_CUDA_ARCHITECTURES=75" in install_env["CMAKE_ARGS"]


def test_default_cuda_architecture_uses_t4_target(monkeypatch):
    monkeypatch.delenv("CUDA_ARCHITECTURES", raising=False)
    monkeypatch.delenv("CUDA_ARCH", raising=False)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")

    install_cmd, install_env = main.build_llama_cpp_install_command(cuda_arch="75")

    assert install_cmd[:4] == [sys.executable, "-m", "pip", "install"]
    assert "--extra-index-url" in install_cmd
    assert "https://abetlen.github.io/llama-cpp-python/whl/cu124" in install_cmd
    assert "llama-cpp-python" in install_cmd
    assert "-DCMAKE_CUDA_ARCHITECTURES=75" in install_env["CMAKE_ARGS"]
