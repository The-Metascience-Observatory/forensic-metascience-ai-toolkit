"""Where docling runs: the image package's accelerator broker, or this process.

The managed accelerator broker (`compute/`: device discovery, persistent GPU
workers, admission, qualification records) belongs to the separately
distributed image analysis package, because its qualification identities hash
that package's files. When it is installed, every call here is the broker's,
unchanged. When it is not, docling runs in this process on the CPU, under an
execution identity that says so (`broker: none`), so a cache written by one
setup is never served as the other's (`docling_tables._execution_identity`).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path

from ..image_plugin import available, load


def _broker(name):
    return load(f"compute.{name}") if available() else None


def digest(value):
    """`compute.contracts.digest`, the same function (cache paths depend on it)."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


class LocalCpu:
    """The execution when no broker is installed: docling here, on the CPU."""
    requested = "cpu"
    device = "cpu"
    workload = "document"
    reason = "no_accelerator_broker"

    def identity(self):
        return {"requested": self.requested, "device": self.device,
                "workload": self.workload, "broker": None}

    def record(self):
        return {**self.identity(), "reason": self.reason}


def resolve(workload):
    m = _broker("devices")
    return m.resolve(workload) if m else LocalCpu()


def workload_signature(workload):
    m = _broker("devices")
    if m:
        return m.workload_signature(workload)
    here = Path(__file__).resolve().parent
    return {"extraction/docling_tables.py": hashlib.sha256(
        (here / "docling_tables.py").read_bytes()).hexdigest(), "broker": None}


def model_manifest():
    m = _broker("document")
    return m.model_manifest() if m else {"recorded": False, "reason": "no_accelerator_broker"}


def in_worker():
    m = _broker("execution")
    return m.in_worker() if m else False


def run(workload, payload, **kwargs):
    return load("compute.execution").run(workload, payload, **kwargs)


def cpu_overflow(execution):
    m = _broker("document")
    return m.cpu_overflow(execution) if m else execution


@contextlib.contextmanager
def gpu_slot():
    m = _broker("document")
    if m is None:
        yield False
        return
    with m.gpu_slot() as held:
        yield held


@contextlib.contextmanager
def admission():
    m = _broker("document")
    if m is None:
        yield
        return
    with m.admission():
        yield


def verify_converter(converter, device):
    m = _broker("document")
    return m.verify_converter(converter, device) if m else None


def ocr_options(device):
    m = _broker("document")
    if m:
        return m.ocr_options(device)
    # The broker's CPU settings (`compute.document.ocr_options`), so a CPU
    # extraction reads the same text with or without the broker installed.
    from docling.datamodel.pipeline_options import RapidOcrOptions
    params = {
        "EngineConfig.onnxruntime.use_cuda": False,
        "EngineConfig.onnxruntime.use_dml": False,
        "EngineConfig.onnxruntime.use_coreml": False,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        "EngineConfig.onnxruntime.intra_op_num_threads": int(
            os.environ.get("METASCIENCE_INFERENCE_THREADS", "4")),
        "EngineConfig.onnxruntime.cuda_ep_cfg.device_id": 0,
        "EngineConfig.onnxruntime.cuda_ep_cfg.use_tf32": False,
        "EngineConfig.onnxruntime.cuda_ep_cfg.gpu_mem_limit": int(
            os.environ.get("METASCIENCE_WORKER_DEVICE_BYTES", str(2**63 - 1))),
        "EngineConfig.onnxruntime.cuda_ep_cfg.cudnn_conv_algo_search": "HEURISTIC",
        "EngineConfig.onnxruntime.cuda_ep_cfg.cudnn_conv_use_max_workspace": False,
        "EngineConfig.onnxruntime.cuda_ep_cfg.arena_extend_strategy": "kSameAsRequested",
    }
    return RapidOcrOptions(backend="onnxruntime", rapidocr_params=params)
