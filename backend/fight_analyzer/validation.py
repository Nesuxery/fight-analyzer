"""Checking an analysis against a small set of manual labels.

    python -m fight_analyzer.validation sheet  <job_id> [--every 10]
        Renders sampled frames with every detected person boxed and numbered
        (no identities, so labelling is not biased by the result) and writes a
        label template next to them: data/validation/<job_id>/.
    python -m fight_analyzer.validation report <job_id> <labels.json>
        Compares the identities and strike attempts of the analysis with the labels
        and prints counts per scenario.

Labels (JSON):
    role        "tuning" (the clip was used while adjusting the method) or
                "evaluation" (never used for adjusting); only the latter says
                anything about accuracy on new footage.
    identity    [{"frame", "red", "blue", "referee", "scenario"}] where red/blue are
                detection numbers on that frame's sheet, null = not visible, -1 = visible
                but without a box of its own (e.g. under the referee); referee is a
                number or a list of numbers (duplicate boxes), null = not visible.
    strikes     [{"frame", "actor": "red"|"blue", "kind": "punch"|"kick"|"knee", "scenario"}]
                every attempt inside "strike_window" [first, last] frame.
Only counts are reported: a handful of labels supports no percentage.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2

from fight_analyzer.config import Settings, load_settings
from fight_analyzer.fsutil import inside
from fight_analyzer.jobs.store import JobStore
from fight_analyzer.media.analysis_video import video_path
from fight_analyzer.motion import store as motion_store
from fight_analyzer.pose.cache import load_arrays, read_manifest
from fight_analyzer.tracking import results as identity_results

STRIKES = {"punch", "kick", "knee"}
SIDES = {"red": 0, "blue": 1}
MATCH_FRAMES = 6  # a detected attempt matches a label within 0.2 s at 30 fps


def _load(job_id: str, settings: Settings | None = None):
    settings = settings or load_settings()
    job = JobStore(settings.db_path).get_job(job_id)
    if job is None or job.outputs.tracking is None or job.outputs.pose is None:
        raise SystemExit(f"{job_id}: no finished analysis with identities in {settings.data_dir}")
    cache = settings.cache_dir
    poses = load_arrays(cache, read_manifest(cache, job.outputs.pose.cache_key), check_hashes=False)
    ident = identity_results.read_arrays(cache, job.outputs.tracking.cache_key)
    return settings, job, poses, ident


def sheet(job_id: str, every: int, settings: Settings | None = None) -> Path:
    settings, job, poses, _ = _load(job_id, settings)
    out = inside(settings.data_dir, "validation", job_id)
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path(settings.cache_dir, job.outputs.analysis_video.cache_key)))
    picks = set(range(0, poses.frame_count, every))
    f = 0
    while picks and f <= max(picks):
        ok, img = cap.read()
        if not ok:
            break
        if f in picks:
            a, b = int(poses.det_offsets[f]), int(poses.det_offsets[f + 1])
            for d in range(b - a):
                x1, y1, x2, y2 = (int(v) for v in poses.boxes[a + d])
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 2)
                cv2.putText(img, str(d), (x1 + 3, y1 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
                cv2.putText(img, str(d), (x1 + 3, y1 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(img, f"frame {f}", (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            cv2.imwrite(str(out / f"frame_{f:06d}.jpg"), img)
        f += 1
    cap.release()
    template = {"clip": job.source.filename if job.source else None, "role": "evaluation",
                "note": "red/blue/referee: detection number on the sheet, null = not visible",
                "identity": [{"frame": x, "red": None, "blue": None, "referee": None, "scenario": ""}
                             for x in sorted(picks) if x < poses.frame_count],
                "strike_window": [0, poses.frame_count - 1], "strikes": []}
    (out / "labels.template.json").write_text(json.dumps(template, indent=1), encoding="utf-8")
    return out


def compare(job_id: str, labels: dict, settings: Settings | None = None) -> dict:
    settings, job, poses, ident = _load(job_id, settings)
    report: dict = {"job_id": job_id, "clip": labels.get("clip"), "role": labels.get("role"),
                    "identity": {}, "strikes": {}}
    # identities on the labelled frames
    outcome: dict[str, Counter] = defaultdict(Counter)
    cases: list[dict] = []
    for row in labels.get("identity", []):
        f = row["frame"]
        first = int(poses.det_offsets[f])
        ref = row.get("referee")
        referee = set(ref) if isinstance(ref, list) else {ref} if ref is not None else set()
        for side, col in SIDES.items():
            truth, other = row.get(side), row.get("blue" if side == "red" else "red")
            state = int(ident["state"][f, col])  # 0 tracked, 1 occluded, 2 uncertain
            det = int(ident["det"][f, col])
            ours = det - first if det >= 0 and state != 2 else None
            if truth is None:
                kind = "doğru: görünmüyor" if ours is None else "görünmüyorken atandı"
            elif ours is None:
                kind = "doğru: kutusu yok, belirsiz" if truth == -1 else "belirsiz (görünüyorken)"
            elif ours == truth:
                kind = "doğru kişi"
            elif ours == other:
                kind = "kimlik karışması"
            elif ours in referee:
                kind = "hakeme kayma"
            else:
                kind = "başka kişi"
            outcome[row.get("scenario") or "-"][kind] += 1
            outcome["toplam"][kind] += 1
            if not kind.startswith("doğru"):
                cases.append({"frame": f, "side": side, "result": kind})
    fps = job.outputs.analysis_video.video.fps
    report["identity"] = {"by_scenario": {k: dict(v) for k, v in outcome.items()}, "problems": cases,
                          "uncertain_s": {f.fighter_id.value: round(f.uncertain_ms / 1000, 2)
                                          for f in job.outputs.tracking.fighters},
                          "frames": int(ident["state"].shape[0]), "fps": fps}
    # strike attempts inside the labelled window
    lo, hi = labels.get("strike_window", [0, -1])
    events = motion_store.read_events(settings.cache_dir, job.outputs.events.cache_key).events if job.outputs.events \
        else []
    side_of = {"fighter_a": "red", "fighter_b": "blue"}
    found = [e for e in events if e.type.value in STRIKES and lo <= (e.peak_frame or e.start_frame) <= hi]
    truth = [s for s in labels.get("strikes", []) if lo <= s["frame"] <= hi]
    # closest pairs first (same fighter, within MATCH_FRAMES), each label and detection used once
    pairs = sorted((abs((e.peak_frame or e.start_frame) - s["frame"]), i, j)
                   for i, s in enumerate(truth) for j, e in enumerate(found)
                   if side_of.get(e.actor) == s["actor"] and abs((e.peak_frame or e.start_frame) - s["frame"]) <= MATCH_FRAMES)
    label_hit: dict[int, int] = {}
    used: set[str] = set()
    for _, i, j in pairs:
        if i not in label_hit and found[j].event_id not in used:
            label_hit[i] = j
            used.add(found[j].event_id)
    tp = [{**s, "detected_frame": found[label_hit[i]].peak_frame, "detected_type": found[label_hit[i]].type.value,
           "possible_contact": found[label_hit[i]].possible_contact}
          for i, s in enumerate(truth) if i in label_hit]
    fn = [s for i, s in enumerate(truth) if i not in label_hit]
    fp = [{"frame": e.peak_frame, "actor": side_of.get(e.actor), "type": e.type.value,
           "confidence": e.confidence} for e in found if e.event_id not in used]
    report["strikes"] = {"window": [lo, hi], "labelled": len(truth), "detected": len(found),
                         "matched": tp, "missed": fn, "false_detections": fp}
    return report


def _print(report: dict) -> None:
    print(f"Klip: {report['clip']}  rol: {report['role']}  (iş {report['job_id']})")
    print("\nKimlik (etiketli karelerde, köşe başına):")
    scenarios = report["identity"]["by_scenario"]
    for scen, counts in sorted(scenarios.items(), key=lambda kv: kv[0] == "toplam"):
        print(f"  {scen:<22} " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    for p in report["identity"]["problems"]:
        print(f"    kare {p['frame']:>5} {p['side']:<4} {p['result']}")
    print(f"  belirsiz takip süresi (tüm video): {report['identity']['uncertain_s']}")
    s = report["strikes"]
    print(f"\nVuruş denemeleri (kare {s['window'][0]}–{s['window'][1]}): etiket {s['labelled']}, tespit "
          f"{s['detected']}, eşleşen {len(s['matched'])}, kaçırılan {len(s['missed'])}, yanlış tespit "
          f"{len(s['false_detections'])}")
    for m in s["matched"]:
        print(f"    eşleşti   kare {m['frame']:>4} {m['actor']:<4} {m['kind']:<5} → tespit {m['detected_frame']}")
    for m in s["missed"]:
        print(f"    kaçırıldı kare {m['frame']:>4} {m['actor']:<4} {m['kind']}")
    for m in s["false_detections"]:
        print(f"    yanlış    kare {m['frame']:>4} {m['actor']:<4} {m['type']} (güven {m['confidence']})")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m fight_analyzer.validation")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_sheet = sub.add_parser("sheet", help="render numbered frames and a label template")
    p_sheet.add_argument("job_id")
    p_sheet.add_argument("--every", type=int, default=10)
    p_rep = sub.add_parser("report", help="compare an analysis with labels")
    p_rep.add_argument("job_id")
    p_rep.add_argument("labels", type=Path)
    p_rep.add_argument("--json", type=Path, help="also write the report as JSON")
    args = parser.parse_args(argv)
    if args.cmd == "sheet":
        print(sheet(args.job_id, max(1, args.every)))
        return 0
    report = compare(args.job_id, json.loads(args.labels.read_text(encoding="utf-8")))
    _print(report)
    if args.json:
        args.json.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

