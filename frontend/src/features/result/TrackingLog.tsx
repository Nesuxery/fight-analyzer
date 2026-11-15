import { useMemo, useState } from "react";
import { navigate } from "../../app/router";
import type { TrackingSummary, UncertainReason } from "../../contracts/generated";
import { TRACKING_LABELS, UI_LABELS, formatDuration, formatNumber } from "../../labels";
import { HelpTip } from "../../ui";
import type { Clock } from "../../player/clock";
import { formatClock } from "../../player/clock";

const REASONS: Record<UncertainReason, string> = {
  camera_cut: "kamera kesimi sonrası tanınamadı",
  overlap: "uzun örtüşme",
  lost: "görünmüyor / tespit yok",
  ambiguous: "dövüşçüler ayırt edilemedi",
  anchor_conflict: "seçimler birbiriyle çelişiyor",
};

const REVIEW: Record<string, string> = {
  reacquired_low_margin: "Kimlik düşük farkla yeniden bulundu",
  swap_corrected: "Takipçinin numara takası görünümle düzeltildi",
  identity_switch: "Olası kimlik değişimi: başka kişinin izi devralındı",
  after_cut: "Kesim sonrası kimlik yalnız görünümle bulundu",
};

type Kind = "uncertain" | "review" | "cut";
interface Entry {
  frame: number;
  kind: Kind;
  side: "red" | "blue" | null;
  text: string;
}

/** Everything worth checking about identities, each with a jump and a fix action. */
export function TrackingLog({ jobId, tracking, cuts, fps, clock, time, names }: {
  jobId: string;
  tracking: TrackingSummary;
  cuts: number[];
  fps: number;
  clock: Clock;
  time: number;
  names: { red: string; blue: string };
}) {
  const [filter, setFilter] = useState<Kind | "all">("all");
  const sideOf = (id: string) => (id === "fighter_a" ? "red" : "blue") as "red" | "blue";
  const entries = useMemo<Entry[]>(() => {
    const out: Entry[] = cuts.map((c) => ({ frame: c, kind: "cut", side: null, text: "Kamera kesimi: konumlar yeni çekime taşınmadı" }));
    for (const seg of tracking.uncertain_segments) {
      const dur = (seg.end_frame - seg.start_frame + 1) / fps;
      out.push({ frame: seg.start_frame, kind: "uncertain", side: sideOf(seg.fighter_id),
                 text: `Takip belirsiz · ${formatDuration(dur < 1 ? Math.max(dur, 0.1) : dur)} · ${REASONS[seg.reason]}` });
    }
    for (const p of tracking.review_points) {
      out.push({ frame: p.frame_index, kind: "review", side: sideOf(p.fighter_id), text: REVIEW[p.kind] ?? p.kind });
    }
    return out.sort((a, b) => a.frame - b.frame);
  }, [tracking, cuts, fps]);
  const shown = entries.filter((e) => filter === "all" || e.kind === filter);
  const current = time * fps;
  const [red, blue] = tracking.fighters;
  const filters: { id: Kind | "all"; label: string }[] = [
    { id: "all", label: "Tümü" }, { id: "uncertain", label: "Belirsiz" },
    { id: "review", label: "Kontrol önerilir" }, { id: "cut", label: "Kesimler" },
  ];

  return (
    <section className="events" aria-label="Takip kaydı">
      <header className="events__head">
        <h2 className="display display--sm">Takip kaydı</h2>
        <div className="chips" role="group" aria-label="Kayıt filtresi">
          {filters.map((f) => (
            <button key={f.id} type="button" className="chipbtn" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
              {f.label}
            </button>
          ))}
        </div>
      </header>
      <dl className="tsum">
        <div><dt>Olası kimlik değişimi</dt><dd className="num">{tracking.identity_switches}</dd></div>
        <div><dt>Takas düzeltmesi</dt><dd className="num">{tracking.swap_corrections}</dd></div>
        <div><dt>Belirsiz · {names.red}</dt><dd className="num">{formatDuration((red?.uncertain_ms ?? 0) / 1000)}</dd></div>
        <div><dt>Belirsiz · {names.blue}</dt><dd className="num">{formatDuration((blue?.uncertain_ms ?? 0) / 1000)}</dd></div>
        <div><dt>Kamera kesimi</dt><dd className="num">{cuts.length}</dd></div>
        <div><dt>Seçim noktası</dt><dd className="num">{tracking.anchors.length}</dd></div>
      </dl>
      <p className="tsum__model">
        {tracking.appearance
          ? TRACKING_LABELS.appearance(tracking.appearance.red_samples, tracking.appearance.blue_samples,
                                       tracking.appearance.third_samples)
          : TRACKING_LABELS.noAppearance}
        {tracking.extra_cuts.length > 0 && ` · ${TRACKING_LABELS.extraCuts(tracking.extra_cuts.length)}`}
        <HelpTip label={UI_LABELS.help(TRACKING_LABELS.appearanceTerm)} align="start">
          {TRACKING_LABELS.appearanceHelp}
        </HelpTip>
      </p>
      {shown.length === 0 ? (
        <p className="events__none">{entries.length ? "Bu filtrede kayıt yok." : "Belirsizlik veya kontrol noktası yok."}</p>
      ) : (
        <ol className="events__list">
          {shown.map((e) => (
            <li key={`${e.kind}-${e.frame}-${e.side}`}
                className={`tlog tlog--${e.kind}${Math.abs(e.frame - current) < fps / 2 ? " is-current" : ""}`}>
              <span className="evt__time num">{formatClock(e.frame / fps, true)}</span>
              <span className={`evt__side evt__side--${e.side ?? "none"}`}>
                {e.side ? names[e.side] : "Video"}
              </span>
              <span className="tlog__text">{e.text}</span>
              <span className="tlog__actions">
                <button type="button" className="btn btn--sm btn--ghost" onClick={() => clock.seek(e.frame / fps)}>Git</button>
                {e.kind !== "cut" && (
                  <button type="button" className="btn btn--sm btn--ghost"
                          title="Bu karede dövüşçüleri yeniden seçerek düzeltin (görünmeyen dövüşçü işaretlenebilir)"
                          onClick={() => navigate({ mode: "analysis", screen: "select", jobId,
                                                    params: { frame: e.frame, keep: true } })}>
                    Bu karede düzelt
                  </button>
                )}
              </span>
            </li>
          ))}
        </ol>
      )}
      <p className="events__foot">Kare {formatNumber(Math.round(current))} · Yanlış bir kimlik görürseniz o karede "Bu karede düzelt" ile yeniden seçin; önceki seçimler korunur.</p>
    </section>
  );
}
