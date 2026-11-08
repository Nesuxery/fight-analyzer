import { useState } from "react";
import { IconDownload, IconEdit, IconSwap, IconTarget } from "../../ui/icons";
import { DemoTag } from "../../ui";
import type { Side } from "../../model/analysis";
import { SIDE_LABEL } from "../../labels";
import type { FighterActions } from "./types";

const MAX_NAME = 40;

function FighterName({ side, name, onRename }: {
  side: Side;
  name: string | null;
  onRename?: (side: Side, name: string) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const save = () => {
    const value = draft?.trim();
    if (value && onRename) onRename(side, value);
    setDraft(null);
  };
  return (
    <div className={`fname fname--${side}`}>
      <span className="fname__corner">{SIDE_LABEL[side]} köşe</span>
      {draft === null ? (
        <div className="fname__row">
          <span className="fname__name display">{name ?? "—"}</span>
          {onRename && name !== null && (
            <button type="button" className="btn btn--icon btn--quiet" onClick={() => setDraft(name)}
                    aria-label={`${SIDE_LABEL[side]} köşe adını değiştir`} title="Adı değiştir">
              <IconEdit size={16} />
            </button>
          )}
        </div>
      ) : (
        <input
          className="fname__input display"
          value={draft}
          maxLength={MAX_NAME}
          autoFocus
          aria-label={`${SIDE_LABEL[side]} köşe dövüşçü adı`}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={save}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") setDraft(null);
          }}
        />
      )}
    </div>
  );
}

/** red: displayed red share in whole percent (blue = 100 - red), null without data. */
function Momentum({ red, demo, insufficient, excluded }: {
  red: number | null;
  demo: boolean;
  insufficient: boolean;
  excluded: boolean;
}) {
  return (
    <div className="momentum">
      <div className="momentum__label">
        <span className="display">Momentum</span>
        <span className="tag tag--muted" title="Ölçülen sinyallerden türetilen deneysel endeks; kazanma olasılığı değildir.">
          Deneysel
        </span>
        {demo && <DemoTag small />}
        {excluded && (
          <span className="tag tag--muted" title="Bu an dışlanan bir bölümde (ör. tekrar): olay sayılmaz, momentum donar.">
            Dışlanan bölüm
          </span>
        )}
        {insufficient && !excluded && (
          <span className="tag tag--amber" title="Bu anda dövüşçülerden biri ölçülemiyor; yeni olay üretilmiyor.">
            Veri yetersiz
          </span>
        )}
      </div>
      <div className="momentum__bar" role="meter" aria-label="Momentum, kırmızı köşe payı"
           aria-valuemin={0} aria-valuemax={100} aria-valuenow={red ?? undefined}
           aria-valuetext={red === null ? "Veri yok" : `Kırmızı %${red}, mavi %${100 - red}`}>
        <span className="momentum__num momentum__num--red num">{red === null ? "—" : `${red}%`}</span>
        <div className="momentum__track">
          {red === null ? <span className="momentum__none" /> : (
            <>
              <span className="momentum__fill momentum__fill--red" style={{ width: `${red}%` }} />
              <span className="momentum__fill momentum__fill--blue" style={{ width: `${100 - red}%` }} />
            </>
          )}
          <span className="momentum__mid" aria-hidden="true" />
        </div>
        <span className="momentum__num momentum__num--blue num">{red === null ? "—" : `${100 - red}%`}</span>
      </div>
      <p className="momentum__caption">Deneysel momentum — kazanma olasılığı değildir</p>
    </div>
  );
}

export function FighterHeader({ names, red, demo, actions, insufficient = false, excluded = false }: {
  names: Record<Side, string> | null;
  /** Red corner's momentum share in whole percent. */
  red: number | null;
  demo: boolean;
  actions: FighterActions;
  insufficient?: boolean;
  /** The presented frame is in a part the user excluded. */
  excluded?: boolean;
}) {
  return (
    <section className="rhead" aria-label="Dövüşçüler ve momentum">
      <FighterName side="red" name={names?.red ?? null} onRename={actions.onRename} />
      <Momentum red={red} demo={demo} insufficient={insufficient} excluded={excluded} />
      <FighterName side="blue" name={names?.blue ?? null} onRename={actions.onRename} />
      <div className="rhead__actions">
        <button type="button" className="btn btn--ghost btn--sm" onClick={actions.onSwap} disabled={!actions.onSwap}>
          <IconSwap size={16} /> Tarafları değiştir
        </button>
        <button type="button" className="btn btn--ghost btn--sm" onClick={actions.onReselect} disabled={!actions.onReselect}>
          <IconTarget size={16} /> Dövüşçüleri yeniden seç
        </button>
        {actions.onExport && (
          <button type="button" className="btn btn--ghost btn--sm" onClick={actions.onExport}>
            <IconDownload size={16} /> Dışa aktar
          </button>
        )}
      </div>
    </section>
  );
}
