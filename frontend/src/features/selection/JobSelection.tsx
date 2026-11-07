import { useEffect, useMemo, useRef, useState } from "react";
import { api, urls } from "../../api/client";
import { navigate } from "../../app/router";
import type { SelectParams } from "../../app/router";
import { StateView } from "../../components/ui";
import type { FighterAnchor, Job, PersonDetection, SelectionCandidates } from "../../contracts/generated";
import { useJob } from "../../hooks/useJob";
import { formatNumber } from "../../labels";
import { NOT_IN_VIEW } from "../../model/analysis";
import type { Assignment, Detection } from "../../model/analysis";
import { formatClock } from "../../player/clock";
import { SelectionLayout } from "./SelectionLayout";

const toDetection = (d: PersonDetection): Detection => ({
  personId: String(d.detection_id), x1: d.bbox.x1, y1: d.bbox.y1, x2: d.bbox.x2, y2: d.bbox.y2,
  confidence: d.confidence,
});

/** Same defaults the API uses until names are set. */
const DEFAULT_NAMES = { red: "Dövüşçü 1", blue: "Dövüşçü 2" };

function savedNames(job: Job): { red: string; blue: string } {
  const red = job.fighters.find((f) => f.fighter_id === "fighter_a")?.display_name;
  const blue = job.fighters.find((f) => f.fighter_id === "fighter_b")?.display_name;
  return { red: red ?? DEFAULT_NAMES.red, blue: blue ?? DEFAULT_NAMES.blue };
}

/**
 * Pick the red and then the blue fighter on a frame of the real analysis
 * video. Candidate frames come from the tracking preparation; any other frame
 * can be reached with the frame steps (used for "fix at this frame"). With
 * `keep`, earlier selections stay and this one is added as a correction.
 */
export function JobSelection({ jobId, params }: { jobId: string; params?: SelectParams }) {
  const job = useJob(jobId, 2000);
  const [cands, setCands] = useState<SelectionCandidates | null>(null);
  const [candError, setCandError] = useState<string | null>(null);
  const [frame, setFrame] = useState<number | null>(params?.frame ?? null);
  const [dets, setDets] = useState<{ frame: number; list: PersonDetection[] } | null>(null);
  const [picks, setPicks] = useState<Assignment>({ red: null, blue: null });
  const [keep, setKeep] = useState(params?.keep ?? false);
  const [names, setNames] = useState<{ red: string; blue: string } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const data = job.data;
  const prepKey = data?.outputs.tracking_prep?.cache_key;
  const video = data?.outputs.analysis_video?.video;

  useEffect(() => {
    if (!prepKey) return;
    const c = new AbortController();
    api.candidates(jobId, c.signal).then(setCands, (e: unknown) => {
      if (!c.signal.aborted) setCandError(e instanceof Error ? e.message : String(e));
    });
    return () => c.abort();
  }, [jobId, prepKey]);

  const current = frame ?? cands?.frames[0]?.frame_index ?? null;

  // Detections of the current frame: from the candidates, otherwise from the pose data.
  useEffect(() => {
    if (current === null) return;
    const fromCand = cands?.frames.find((f) => f.frame_index === current);
    if (fromCand) {
      setDets({ frame: current, list: fromCand.detections });
      return;
    }
    const c = new AbortController();
    api.poses(jobId, current, 1, c.signal).then(
      (chunk) => setDets({ frame: current, list: chunk.frames[0]?.detections ?? [] }),
      () => undefined,
    );
    return () => c.abort();
  }, [jobId, current, cands]);

  // Show exactly that frame of the analysis video.
  useEffect(() => {
    const el = videoRef.current;
    if (!el || current === null || !video) return;
    const seek = () => { el.currentTime = (current + 0.5) / video.fps; };
    if (el.readyState >= 1) seek();
    else el.addEventListener("loadedmetadata", seek, { once: true });
  }, [current, video]);

  useEffect(() => {
    if (!names && data) setNames(savedNames(data));
  }, [data, names]);

  const existing = data?.selection?.anchors ?? [];
  const sortedCands = useMemo(() => (cands?.frames ?? []).map((f) => f.frame_index).sort((a, b) => a - b), [cands]);

  if (job.loading) return <StateView tone="loading" title="Analiz bilgisi yükleniyor…" />;
  if (job.notFound) {
    return <StateView tone="error" title="Analiz bulunamadı" action={<a className="btn btn--ghost" href="#/">Yükleme ekranına dön</a>} />;
  }
  if (!data) return <StateView tone="error" title="Analiz durumu alınamadı">API'ye ulaşılamıyor; yeniden deneniyor.</StateView>;
  if (data.status === "queued" || data.status === "running") {
    return (
      <StateView tone="loading" title="Analiz işleniyor"
                 action={<a className="btn btn--ghost" href={`#/analyses/${jobId}/processing`}>İşlem ekranını aç</a>}>
        Seçim, poz tespiti ve takip hazırlığı bittiğinde yapılabilir.
      </StateView>
    );
  }
  if (!data.outputs.pose || !video) {
    return <StateView tone="empty" title="Seçim için poz verisi yok">Bu analizde poz tespiti tamamlanmamış.</StateView>;
  }
  if (!prepKey) {
    return (
      <StateView tone="empty" title="Aday kareler hazırlanmamış"
                 action={<button type="button" className="btn btn--primary"
                                 onClick={() => api.retry(jobId).then(() => navigate({ mode: "analysis", screen: "processing", jobId }))}>
                   Aday kareleri hazırla</button>}>
        Bu analiz, takip hazırlığı eklenmeden önce yapılmış. Önbellekteki pozlar kullanılarak hızlıca hazırlanabilir.
      </StateView>
    );
  }
  if (candError) return <StateView tone="error" title="Aday kareler alınamadı">{candError}</StateView>;
  if (!cands || current === null) return <StateView tone="loading" title="Aday kareler yükleniyor…" />;

  const lastFrame = video.frame_count - 1;
  const goTo = (f: number) => {
    setFrame(Math.min(lastFrame, Math.max(0, f)));
    setPicks({ red: null, blue: null });
    setProblem(null);
  };
  const prevCand = [...sortedCands].reverse().find((f) => f < current);
  const nextCand = sortedCands.find((f) => f > current);
  const candIndex = sortedCands.indexOf(current);
  const label = candIndex >= 0
    ? `Aday ${candIndex + 1} / ${sortedCands.length} · ${formatClock(current / video.fps, true)}`
    : `Kare ${formatNumber(current)} · ${formatClock(current / video.fps, true)}`;
  const detsLoaded = dets !== null && dets.frame === current;
  const frameDets = detsLoaded ? dets.list : [];

  const confirm = async () => {
    if (picks.red === null || picks.blue === null) return;
    const detId = (pick: string) => (pick === NOT_IN_VIEW ? null : Number(pick));
    const anchor: FighterAnchor = { frame_index: current, red_detection_id: detId(picks.red),
                                    blue_detection_id: detId(picks.blue) };
    const anchors = keep ? [...existing.filter((a) => a.frame_index !== current), anchor] : [anchor];
    setBusy(true);
    setProblem(null);
    try {
      if (names && (names.red.trim() && names.blue.trim())) {
        const saved = savedNames(data);
        const changed = saved.red !== names.red.trim() || saved.blue !== names.blue.trim();
        if (changed) await api.setNames(jobId, { red: names.red.trim(), blue: names.blue.trim() });
      }
      await api.submitSelection(jobId, { anchors });
      navigate({ mode: "analysis", screen: "processing", jobId });
    } catch (e) {
      setProblem(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const step = (n: number) => (
    <button type="button" className="btn btn--sm btn--ghost" onClick={() => goTo(current + n)}
            title={`${n > 0 ? "+" : ""}${n} kare`}>
      {n > 0 ? `+${n}` : n}
    </button>
  );

  return (
    <SelectionLayout
      title={<>{data.source?.filename ?? `Analiz ${jobId.slice(0, 8)}`}</>}
      picks={picks}
      onPick={(p) => {
        setProblem(null);
        setPicks(p);
      }}
      detections={frameDets.map(toDetection)}
      frame={{ width: video.width, height: video.height }}
      stage={(boxes) => (
        <div className="stage" style={{ aspectRatio: `${video.width} / ${video.height}` }}>
          <video ref={videoRef} className="stage__video" src={urls.video(jobId)} muted playsInline preload="auto" />
          {boxes}
          {!detsLoaded && <div className="stage__veil">Kişiler yükleniyor…</div>}
          {detsLoaded && frameDets.length === 0 && <div className="stage__veil">Bu karede kişi tespit edilmedi</div>}
        </div>
      )}
      candidateLabel={label}
      onPrev={prevCand !== undefined ? () => goTo(prevCand) : undefined}
      onNext={nextCand !== undefined ? () => goTo(nextCand) : undefined}
      navExtra={<span className="select__steps">{step(-10)}{step(-1)}{step(1)}{step(10)}</span>}
      onConfirm={() => void confirm()}
      busy={busy}
      problem={problem}
      confirmLabel={keep && existing.length ? "Düzeltmeyi ekle ve yeniden eşle" : "Onayla ve takibi başlat"}
      allowNotInView={keep && existing.length > 0}
      extra={
        <div className="select__extra">
          {names && (
            <div className="names">
              <label className="names__field names__field--red">
                <span>Kırmızı köşe adı</span>
                <input value={names.red} maxLength={40} onChange={(e) => setNames({ ...names, red: e.target.value })} />
              </label>
              <label className="names__field names__field--blue">
                <span>Mavi köşe adı</span>
                <input value={names.blue} maxLength={40} onChange={(e) => setNames({ ...names, blue: e.target.value })} />
              </label>
            </div>
          )}
          {existing.length > 0 && (
            <div className="anchors">
              <label className="anchors__keep">
                <input type="checkbox" checked={keep} onChange={(e) => setKeep(e.target.checked)} />
                Önceki seçimleri koru (düzeltme olarak ekle)
              </label>
              <ul className="anchors__list">
                {existing.map((a) => (
                  <li key={a.frame_index}>
                    <button type="button" className="linkbtn" onClick={() => goTo(a.frame_index)}>
                      Kare {formatNumber(a.frame_index)} · {formatClock(a.frame_index / video.fps, true)}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      }
    />
  );
}
