"""Real worker process with a CPU-heavy stand-in handler (test use only).

It saturates the CPU with matrix multiplications for FA_TEST_BUSY_SECONDS and
reports progress, so tests can check the API stays responsive meanwhile.
"""

from __future__ import annotations

import os
import time

import numpy as np

from fight_analyzer.contracts import JobType, PipelineStage
from fight_analyzer.jobs.worker import JobContext, main


def busy(ctx: JobContext) -> None:
    seconds = float(os.environ.get("FA_TEST_BUSY_SECONDS", "4"))
    a = np.random.default_rng(0).random((1200, 1200))
    start = time.perf_counter()
    while (elapsed := time.perf_counter() - start) < seconds:
        # cos keeps values in [cos 1, 1]; a decaying map (tanh) reaches denormals after
        # ~9 rounds and one matmul then takes minutes.
        a = np.cos(a @ a / a.shape[0])
        ctx.report(elapsed / seconds, f"busy {elapsed:.1f}s", stage=PipelineStage.pose)


if __name__ == "__main__":
    main({JobType.analysis: busy})
