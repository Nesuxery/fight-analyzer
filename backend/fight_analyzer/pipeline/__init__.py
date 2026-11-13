"""Analysis pipeline. Stages run in order inside the worker process; each
stage module exposes STAGE and run(ctx).

Video preparation, pose extraction, tracking preparation and the broadcast
analysis (scorebug clock, rounds) run first; the job then waits for the user to pick the two fighters. With a selection the
identity tracking, motion/event analysis and the experimental momentum run
(fast: everything before them is cached). Exports run as separate jobs
(pipeline.export.run_export).
"""

from __future__ import annotations

from fight_analyzer.contracts import FighterSelection
from fight_analyzer.jobs.worker import JobAwaitingInput, JobContext

from . import broadcast, events, pose, scoring, tracking, tracking_prep, video_prep

STAGES = (video_prep, pose, tracking_prep, broadcast, tracking, events, scoring)
BEFORE_SELECTION = (video_prep, pose, tracking_prep, broadcast)


def run_analysis(ctx: JobContext) -> None:
    for stage in BEFORE_SELECTION:
        stage.run(ctx)
    selection = ctx.params.get("selection")
    if not selection:
        raise JobAwaitingInput("Pozlar hazır; dövüşçü seçimi bekleniyor.")
    tracking.run(ctx, FighterSelection.model_validate(selection))
    events.run(ctx)
    scoring.run(ctx)
