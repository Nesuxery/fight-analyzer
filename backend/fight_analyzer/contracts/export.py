"""Write the combined JSON Schema of all top-level contracts.

    python -m fight_analyzer.contracts.export          # write
    python -m fight_analyzer.contracts.export --check  # exit 1 if out of date
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic.json_schema import models_json_schema

from . import (
    COCO17_KEYPOINT_NAMES,
    ErrorResponse,
    AnalysisExport,
    EventTimeline,
    ExportRequest,
    MatchSetup,
    Scorecards,
    SegmentExclusions,
    MomentumTimeline,
    MotionTimeline,
    FighterNames,
    FighterSelection,
    SelectionCandidates,
    TrackingTimeline,
    HealthResponse,
    Job,
    JobList,
    PoseCacheManifest,
    PoseChunk,
    PosePreview,
    PoseSequence,
    UploadLimits,
)
from .common import SCHEMA_VERSION

TOP_LEVEL_MODELS = (HealthResponse, Job, JobList, PoseSequence, PoseChunk, PosePreview,
                    PoseCacheManifest, UploadLimits, ErrorResponse, EventTimeline,
                    SelectionCandidates, FighterSelection, FighterNames, TrackingTimeline,
                    MotionTimeline, MomentumTimeline, ExportRequest, AnalysisExport,
                    SegmentExclusions, MatchSetup, Scorecards)

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "shared"
    / "schemas"
    / f"fight-analyzer.v{SCHEMA_VERSION.split('.')[0]}.schema.json"
)


def build_schema() -> dict:
    _, defs = models_json_schema(
        [(model, "serialization") for model in TOP_LEVEL_MODELS],
        ref_template="#/$defs/{model}",
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FightAnalyzerContracts",
        "description": f"MMA Fight Analyzer data contracts, schema version {SCHEMA_VERSION}.",
        "x-schema-version": SCHEMA_VERSION,
        "x-keypoint-order": list(COCO17_KEYPOINT_NAMES),
        "type": "object",
        "additionalProperties": False,
        "properties": {m.__name__: {"$ref": f"#/$defs/{m.__name__}"} for m in TOP_LEVEL_MODELS},
        "$defs": defs["$defs"],
    }


def render() -> str:
    return json.dumps(build_schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="only verify the file is current")
    args = parser.parse_args()
    content = render()
    if args.check:
        current = SCHEMA_PATH.read_text(encoding="utf-8") if SCHEMA_PATH.exists() else ""
        if current != content:
            print(f"{SCHEMA_PATH} is out of date; run python -m fight_analyzer.contracts.export")
            return 1
        print(f"{SCHEMA_PATH.name} is up to date")
        return 0
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {SCHEMA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
