import type { ReactNode } from "react";
import { IconBack, IconForward, IconFrameNext, IconFramePrev, IconPause, IconPlay } from "../../components/icons";
import type { Clock, ClockSnapshot } from "../../player/clock";
import { formatClock } from "../../player/clock";
import type { Layers } from "../../player/draw";
import { frameAt } from "../../player/geometry";

const RATES = [0.25, 0.5, 1, 2];
const LAYER_LABELS: { key: keyof Layers; label: string; shortcut: string }[] = [
  { key: "skeleton", label: "İskelet", shortcut: "S" },
  { key: "strikes", label: "Olay efektleri", shortcut: "E" },
  { key: "distance", label: "Mesafe", shortcut: "D" },
];

export function PlaybackBar({ clock, snap, layers, onLayers, disabled, layerKeys, extra, syncNote = null }: {
  clock: Clock;
  snap: ClockSnapshot;
  layers: Layers;
  onLayers: (next: Layers) => void;
  disabled: boolean;
  /** Layers this data can show (default: all). */
  layerKeys?: (keyof Layers)[];
  extra?: ReactNode;
  /** Shown when the overlay cannot follow presented frames exactly (fallback sync). */
  syncNote?: string | null;
}) {
  const frame = frameAt(snap.time, clock.fps, Math.round(clock.duration * clock.fps));
  return (
    <div className="pbar" aria-label="Oynatma kontrolleri">
      <div className="pbar__group">
        <button type="button" className="btn btn--icon" disabled={disabled} onClick={() => clock.skip(-1)}
                aria-label="1 saniye geri" title="1 sn geri (←, Shift+← 5 sn)"><IconBack /></button>
        <button type="button" className="btn btn--icon" disabled={disabled} onClick={() => clock.stepFrames(-1)}
                aria-label="Bir kare geri" title="Bir kare geri (,)"><IconFramePrev /></button>
        <button type="button" className="btn btn--play" disabled={disabled} onClick={() => clock.toggle()}
                aria-label={snap.playing ? "Duraklat" : "Oynat"} title="Oynat/duraklat (Boşluk)">
          {snap.playing ? <IconPause size={20} /> : <IconPlay size={20} />}
        </button>
        <button type="button" className="btn btn--icon" disabled={disabled} onClick={() => clock.stepFrames(1)}
                aria-label="Bir kare ileri" title="Bir kare ileri (.)"><IconFrameNext /></button>
        <button type="button" className="btn btn--icon" disabled={disabled} onClick={() => clock.skip(1)}
                aria-label="1 saniye ileri" title="1 sn ileri (→, Shift+→ 5 sn)"><IconForward /></button>
        <span className="pbar__time num" aria-live="off">
          {formatClock(snap.time, true)} <span className="pbar__dur">/ {formatClock(clock.duration, true)}</span>
        </span>
        <span className="pbar__frame num">Kare {disabled ? "—" : frame.toLocaleString("tr-TR")}</span>
        {syncNote && <span className="tag tag--amber" title={syncNote}>Yedek senkron</span>}
        <label className="pbar__rate">
          <span className="sr-only">Oynatma hızı</span>
          <select value={snap.rate} disabled={disabled} onChange={(e) => clock.setRate(Number(e.target.value))}>
            {RATES.map((r) => <option key={r} value={r}>{r.toLocaleString("tr-TR")}×</option>)}
          </select>
        </label>
      </div>
      <div className="pbar__group pbar__layers" role="group" aria-label="Görüntü katmanları">
        {LAYER_LABELS.filter(({ key }) => !layerKeys || layerKeys.includes(key)).map(({ key, label, shortcut }) => (
          <button key={key} type="button" className="toggle" aria-pressed={layers[key]} disabled={disabled}
                  title={`${label} katmanı (${shortcut})`}
                  onClick={() => onLayers({ ...layers, [key]: !layers[key] })}>
            <span className="toggle__dot" aria-hidden="true" />{label}
          </button>
        ))}
        {extra}
      </div>
    </div>
  );
}
