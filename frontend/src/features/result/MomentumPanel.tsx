import { useMemo } from "react";
import type { FightEvent, MomentumContribution, MomentumParameters } from "../../contracts/generated";
import { EVENT_LABELS, formatNumber } from "../../labels";
import type { Side } from "../../model/analysis";
import { SOURCE_LABELS, breakdown, eventEffect, eventMoment, redShare, totals } from "../../model/measured";
import type { Intervals } from "../../model/measured";
import { formatClock } from "../../player/clock";
import { SIDE_LABEL } from "../../theme";

const pts = (v: number) => formatNumber(v, v >= 10 ? 1 : 2);

/**
 * Why the momentum is where it is: the formula, each side's current points
 * by source, and what the selected event contributes right now.
 */
export function MomentumPanel({ contribs, params, tMs, names, selected, iv = [] }: {
  contribs: MomentumContribution[];
  params: MomentumParameters;
  tMs: number;
  /** Excluded parts: the momentum runs on fight time. */
  iv?: Intervals;
  names: Record<Side, string>;
  selected: FightEvent | null;
}) {
  const m = totals(contribs, tMs, params, iv);
  const red = redShare(m, params.prior);
  const parts = useMemo(() => breakdown(contribs, tMs, params, iv), [contribs, tMs, params, iv]);
  // Effect when it happened, and what is left of it now (points decay).
  const moment = selected ? eventMoment(selected) : 0;
  const effect = selected ? eventEffect(contribs, selected.event_id, moment, params, iv) : null;
  const effectNow = selected && tMs >= moment ? eventEffect(contribs, selected.event_id, tMs, params, iv) : null;
  const prior = formatNumber(params.prior, 0);

  return (
    <section className="mpanel" aria-label="Momentum açıklaması">
      <p className="mpanel__formula">
        Kırmızı payı = 100 × (m₁ + {prior}) / (m₁ + m₂ + {formatNumber(params.prior * 2, 0)}), mavi = 100 − kırmızı.
        Her puan {formatNumber(params.half_life_s, 0)} saniyede yarıya iner. Şu an: m₁ = <b className="num">{pts(m.red)}</b>,
        m₂ = <b className="num">{pts(m.blue)}</b> → <b className="num">%{Math.round(red)}</b> / <b className="num">%{100 - Math.round(red)}</b>.
      </p>

      <div className="mpanel__sides">
        {(["red", "blue"] as const).map((side) => (
          <div key={side} className={`mpanel__side mpanel__side--${side}`}>
            <p className="mpanel__name">{names[side]} <span className="mpanel__corner">{SIDE_LABEL[side]}</span></p>
            {parts[side].length === 0 ? (
              <p className="mpanel__none">Henüz puan yok</p>
            ) : (
              <table className="mpanel__table">
                <thead><tr><th>Kaynak</th><th className="num">Kazanılan</th><th className="num">Şu an</th></tr></thead>
                <tbody>
                  {parts[side].map((p) => (
                    <tr key={p.source}>
                      <td>{SOURCE_LABELS[p.source]}</td>
                      <td className="num">{pts(p.earned)}</td>
                      <td className="num">{pts(p.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>

      <div className="mpanel__event">
        {selected === null ? (
          <p className="mpanel__hint">Olay listesinden bir olay seçin: bu olayın puanı ve şu anki etkisi burada açıklanır.</p>
        ) : (
          <>
            <p className="mpanel__evtitle">
              <span className="num">{formatClock((selected.peak_ms ?? selected.start_ms) / 1000, true)}</span>{" "}
              {EVENT_LABELS[selected.type]}
              {selected.possible_contact && <span className="tag tag--amber">Olası temas</span>}
            </p>
            {effect === null ? (
              <p className="mpanel__none">
                {selected.type === "knockdown" || selected.type === "takedown"
                  ? `Puan yok: kanıt yeterli değil (güven %${Math.round(selected.confidence * 100)}, eşik %${Math.round(params.min_major_confidence * 100)}).`
                  : "Bu olay momentum puanı üretmez."}
              </p>
            ) : (
              <>
                <ul className="mpanel__entries">
                  {effect.entries.map((c) => (
                    <li key={c.contribution_id}>
                      {SOURCE_LABELS[c.source]}: <b className="num">+{pts(c.points)}</b> puan
                    </li>
                  ))}
                </ul>
                <p>
                  {names[effect.side]} için toplam <b className="num">{pts(effect.points)}</b> puan. Olay anında{" "}
                  {names[effect.side]} payını <b className="num">{formatNumber(Math.abs(effect.redDelta), 1)}</b> yüzde
                  puan artırdı.{" "}
                  {effectNow ? (
                    <>
                      Şu an ({formatClock(tMs / 1000, true)}) değeri <b className="num">{pts(effectNow.now)}</b> puan;
                      payı <b className="num">{formatNumber(Math.abs(effectNow.redDelta), 1)}</b> yüzde puan
                      etkiliyor.
                    </>
                  ) : (
                    <>Oynatma henüz bu olaya gelmedi.</>
                  )}
                </p>
              </>
            )}
            {Object.keys(selected.measures).length > 0 && (
              <dl className="mpanel__measures">
                {Object.entries(selected.measures).map(([k, v]) => (
                  <div key={k}><dt>{MEASURE_LABELS[k] ?? k}</dt><dd className="num">{formatNumber(v, 2)}</dd></div>
                ))}
              </dl>
            )}
          </>
        )}
      </div>

      <details className="mpanel__params">
        <summary>Model parametreleri (başlangıç tasarım değerleri; doğrulanmış ağırlıklar değildir)</summary>
        <dl>
          <div><dt>Vuruş denemesi (yumruk, diz)</dt><dd className="num">{pts(params.strike_attempt)}</dd></div>
          <div><dt>Tekme denemesi (ayrıca yumruk sayılmaz)</dt><dd className="num">{pts(params.kick_attempt)}</dd></div>
          <div><dt>Olası temas eki</dt><dd className="num">{pts(params.contact_bonus)}</dd></div>
          <div><dt>İlerleme (saniye başına)</dt><dd className="num">{pts(params.advance_per_s)}</dd></div>
          <div><dt>Tahmini yer kontrolü (saniye başına)</dt><dd className="num">{pts(params.control_per_s)}</dd></div>
          <div><dt>Olası knockdown</dt><dd className="num">{pts(params.knockdown)}</dd></div>
          <div><dt>Olası takedown</dt><dd className="num">{pts(params.takedown)}</dd></div>
          <div><dt>Büyük olay için en düşük güven</dt><dd className="num">%{Math.round(params.min_major_confidence * 100)}</dd></div>
          <div><dt>Yarı ömür</dt><dd className="num">{formatNumber(params.half_life_s, 0)} sn</dd></div>
          <div><dt>Başlangıç payı (iki tarafa)</dt><dd className="num">{pts(params.prior)}</dd></div>
        </dl>
      </details>
    </section>
  );
}

const MEASURE_LABELS: Record<string, string> = {
  peak_speed: "Tepe hız (gövde boyu/sn)",
  extension: "Rakibe uzanma (uzuv boyu)",
  toward: "Rakibe yönelim (kosinüs)",
  distance: "Mesafe (gövde boyu)",
  duration_s: "Süre (sn)",
  raise: "Ayak yüksekliği (gövde boyu)",
  knee_height: "Diz yüksekliği (gövde boyu)",
  seconds: "Süre (sn)",
  fall_s: "Düşüş süresi (sn)",
  strike_before_s: "Vuruştan sonra (sn)",
  possible_contact: "Öncesinde olası temas",
  close_s: "Yakın temas (sn)",
  on_top_after: "Sonrasında üstte",
};
