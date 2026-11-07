"""CSV (one row per frame) and JSON (events, momentum ledger, settings) of an export."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from fight_analyzer.contracts import AnalysisExport, FightEvent, FighterId, MotionTimeline

from .frames import SIDES, FrameMetrics, event_frame

STATES = ("tracked", "occluded", "uncertain")

# Column -> meaning (also written into the JSON file). Empty cell = no valid measurement.
CSV_COLUMNS: dict[str, str] = {
    "frame": "Kare numarası (analiz videosu, 0'dan başlar)",
    "time_s": "Karenin video zamanı, saniye (kare / fps)",
    "red_share": "Ekranda gösterilen deneysel momentum, kırmızı köşe yüzdesi (tam sayı)",
    "blue_share": "Ekranda gösterilen deneysel momentum, mavi köşe yüzdesi (100 - kırmızı)",
    "red_share_exact": "Kırmızı köşe payının yuvarlanmamış değeri, %",
    "momentum_red": "Kırmızı köşenin sönümlenmiş momentum puanı",
    "momentum_blue": "Mavi köşenin sönümlenmiş momentum puanı",
    "momentum_insufficient": "1 = bu anda dövüşçülerden biri ölçülemiyor (veri yetersiz)",
    "excluded": "1 = kullanıcının dışladığı bölüm (tekrar vb.): olay sayılmaz, puan ve süre birikmez",
    "camera_known": "1 = kamera hareketi arka plandan kestirilebildi (10 Hz örnek)",
    "distance_body": "Kalça merkezleri arası mesafe, gövde boyu (10 Hz örnek)",
}
_SIDE_COLUMNS: dict[str, str] = {
    "identity": "Kimlik durumu: tracked (takipte), occluded (örtüşme), uncertain (belirsiz)",
    "measured": "1 = dövüşçü bu örnekte güvenilir ölçüldü (10 Hz örnek)",
    "strike_attempts": "Bu kareye kadar yumruk ve diz denemeleri",
    "kick_attempts": "Bu kareye kadar tekme denemeleri",
    "possible_contacts": "Bu kareye kadar olası temaslı denemeler (2B örtüşme, temas kesin değil)",
    "knockdowns": "Bu kareye kadar olası knockdown",
    "takedowns": "Bu kareye kadar olası takedown",
    "activity_pct": "Ortalama el/ayak hareketliliği, % (3 sn'den az ölçümde boş)",
    "pressure_pct": "İlerleyerek geçen ölçülen süre payı, %",
    "advance_pct": "Hareket ederken ilerleme payı, %",
    "retreat_pct": "Hareket ederken geri çekilme payı, %",
    "control_s": "Tahmini yer kontrolü, saniye (yuvarlanmış)",
    "measured_s": "Bu kareye kadar güvenilir ölçülen süre, saniye",
    "hand_speed": "Bileklerin kalçaya göre hızı, gövde boyu/sn (10 Hz örnek)",
    "foot_speed": "Ayak bileklerinin kalçaya göre hızı, gövde boyu/sn (10 Hz örnek)",
    "approach_speed": "Rakibe doğru (+) / uzağa (-) hız, gövde boyu/sn (10 Hz örnek)",
    "movement": "advancing / retreating / neutral (10 Hz örnek)",
    "posture": "standing / grounded / transition (10 Hz örnek)",
}
for _side, _label in (("red", "Kırmızı"), ("blue", "Mavi")):
    for _name, _meaning in _SIDE_COLUMNS.items():
        CSV_COLUMNS[f"{_side}_{_name}"] = f"{_label} köşe: {_meaning}"
CSV_COLUMNS["events"] = "Tepe anı bu karede olan olaylar: tür:köşe:olay_kimliği (; ile ayrılmış)"


def _num(v, digits: int) -> str:
    if v is None:
        return ""
    f = float(v)
    return "" if not math.isfinite(f) else f"{f:.{digits}f}"


def _int(v) -> str:
    f = float(v)
    return "" if not math.isfinite(f) else str(int(f))


def _flag(v) -> str:
    return "" if v is None else ("1" if v else "0")


def write_csv(path: Path, metrics: FrameMetrics, motion: MotionTimeline, events: Sequence[FightEvent],
              ident_state: np.ndarray | None) -> None:
    at_frame: dict[int, list[str]] = defaultdict(list)
    for e in events:
        side = "red" if e.actor == FighterId.fighter_a else "blue" if e.actor == FighterId.fighter_b else "-"
        at_frame[event_frame(e)].append(f"{e.type.value}:{side}:{e.event_id}")
    signals = {("red" if f.fighter_id == FighterId.fighter_a else "blue"): f for f in motion.fighters}
    with path.open("w", encoding="utf-8", newline="") as fh:
        out = csv.writer(fh)
        out.writerow(CSV_COLUMNS)
        for k, frame in enumerate(metrics.frames.tolist()):
            j = int(metrics.motion_sample[k])
            row = [frame, f"{metrics.t_ms[k] / 1000:.3f}", int(metrics.red_shown[k]), 100 - int(metrics.red_shown[k]),
                   f"{metrics.red_share[k]:.4f}", f"{metrics.m[0, k]:.4f}", f"{metrics.m[1, k]:.4f}",
                   _flag(bool(metrics.insufficient[k])), _flag(bool(metrics.excluded[k])),
                   _flag(motion.camera_known[j]) if j >= 0 else "",
                   _num(motion.distance[j], 3) if j >= 0 else ""]
            for f_idx, side in enumerate(SIDES):
                st = metrics.stats[side]
                sig = signals.get(side)
                state = ""
                if ident_state is not None and frame < ident_state.shape[0]:
                    state = STATES[int(ident_state[frame, f_idx])]
                sample = j >= 0 and sig is not None
                row += [state, _flag(sig.valid[j]) if sample else "",
                        int(st["strike_attempts"][k]), int(st["kick_attempts"][k]), int(st["possible_contacts"][k]),
                        int(st["knockdowns"][k]), int(st["takedowns"][k]),
                        _int(st["activity"][k]), _int(st["pressure"][k]), _int(st["advance"][k]),
                        _int(st["retreat"][k]), int(st["control_s"][k]), f"{st['measured_s'][k]:.1f}",
                        _num(sig.hand_speed[j], 3) if sample else "", _num(sig.foot_speed[j], 3) if sample else "",
                        _num(sig.approach_speed[j], 3) if sample else "",
                        (sig.movement[j] or "") if sample else "", (sig.posture[j] or "") if sample else ""]
            row.append(";".join(at_frame.get(frame, [])))
            out.writerow(row)


def write_bundle(path: Path, bundle: AnalysisExport) -> None:
    path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
