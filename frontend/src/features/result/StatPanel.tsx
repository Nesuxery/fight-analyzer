import type { ReactNode } from "react";
import { DemoTag } from "../../ui";
import type { Side, StatsView } from "../../model/analysis";
import { formatClock } from "../../player/clock";
import { SIDE_LABEL } from "../../labels";

const dash = "—";

/** Value with a unit suffix; the unit is omitted when there is no value. */
function V({ value, unit }: { value: number | null; unit: string }) {
  return value === null ? <>{dash}</> : <>{value}<small>{unit}</small></>;
}

function Meter({ value, side }: { value: number | null; side: Side }) {
  return (
    <span className={`meter meter--${side}`} aria-hidden="true">
      <span className="meter__fill" style={{ width: `${value ?? 0}%` }} />
    </span>
  );
}

export function StatPanel({ side, name, stats, untilS, demo, emptyNote = "Ölçüm verisi yok", extra }: {
  side: Side;
  name: string | null;
  stats: StatsView;
  untilS: number | null;
  demo: boolean;
  emptyNote?: string;
  extra?: ReactNode;
}) {
  const s = stats;
  const hasData = Object.values(s).some((v) => v !== null);
  return (
    <section className={`stats stats--${side}`} aria-label={`${SIDE_LABEL[side]} köşe istatistikleri`}>
      <header className="stats__head">
        <span className="stats__corner">{SIDE_LABEL[side]}</span>
        <span className="stats__name display" title={name ?? undefined}>{name ?? dash}</span>
        {demo && <DemoTag small />}
      </header>
      <dl className="stats__list">
        <div className="stat">
          <dt>Vuruş denemeleri</dt>
          <dd className="stat__big num">{s.strikeAttempts ?? dash}</dd>
        </div>
        <div className="stat">
          <dt>Tekmeler</dt>
          <dd className="stat__big num">{s.kicks ?? dash}</dd>
        </div>
        <div className="stat stat--meter">
          <dt>Aktivite</dt>
          <dd className="num"><V value={s.activity} unit="/100" /></dd>
          <Meter value={s.activity} side={side} />
        </div>
        <div className="stat stat--meter">
          <dt>Baskı</dt>
          <dd className="num"><V value={s.pressure} unit="%" /></dd>
          <Meter value={s.pressure} side={side} />
        </div>
        <div className="stat stat--split">
          <dt>İlerleme / geri çekilme</dt>
          <dd className="num">
            <V value={s.advance} unit="%" /> <span className="stat__sep">/</span> <V value={s.retreat} unit="%" />
          </dd>
          <span className={`split split--${side}`} aria-hidden="true">
            <span className="split__adv" style={{ width: `${s.advance ?? 0}%` }} />
            <span className="split__ret" style={{ width: `${s.retreat ?? 0}%` }} />
          </span>
        </div>
        <div className="stat">
          <dt>Tahmini kontrol süresi</dt>
          <dd className="num">{s.controlS === null ? dash : formatClock(s.controlS)}</dd>
        </div>
        <div className="stat stat--amber">
          <dt>Olası büyük olaylar</dt>
          <dd className="stat__big num">{s.significant ?? dash}</dd>
        </div>
      </dl>
      <footer className="stats__foot">
        {hasData && untilS !== null ? `00:00 – ${formatClock(untilS)} arası` : emptyNote}
      </footer>
      {extra}
    </section>
  );
}
