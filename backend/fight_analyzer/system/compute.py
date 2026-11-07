"""Inference device selection. Imports torch, so only the worker calls this."""

from __future__ import annotations

import os
import platform

from fight_analyzer.config import DevicePreference
from fight_analyzer.contracts import ComputeInfo


def _cpu_name() -> str:
    if platform.system() == "Windows":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    return platform.processor() or "CPU"


def detect_compute(preference: DevicePreference = "auto") -> ComputeInfo:
    """Use CUDA when available (unless 'cpu' is forced), otherwise the CPU."""
    import torch

    cuda_available = torch.cuda.is_available()
    note = None
    if preference == "cuda" and not cuda_available:
        note = "CUDA istendi ama bu bilgisayarda kullanılamıyor; CPU kullanılıyor."
    use_cuda = cuda_available and preference != "cpu"
    return ComputeInfo(
        device="cuda" if use_cuda else "cpu",
        device_name=torch.cuda.get_device_name(0) if use_cuda else _cpu_name(),
        requested=preference,
        cuda_available=cuda_available,
        torch_version=torch.__version__,
        cuda_version=torch.version.cuda,
        cpu_threads=torch.get_num_threads() or os.cpu_count() or 1,
        note=note,
    )
