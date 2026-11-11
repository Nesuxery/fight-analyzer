import { useState } from "react";
import { RESULT_LABELS, SIDE_LABEL, UI_LABELS } from "../../labels";
import type { Side } from "../../model/analysis";
import { Badge, DemoTag, HelpTip } from "../../ui";
import { IconDownload, IconEdit, IconSwap, IconTarget } from "../../ui/icons";
import type { FighterActions } from "./types";

const H = RESULT_LABELS.header;
const M = RESULT_LABELS.momentum;
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
      <Badge tone={side} solid className="fname__corner">{H.corner(SIDE_LABEL[side])}</Badge>
      {draft === null ? (
        <div className="fname__row">
          <span className="fname__name display">{name ?? UI_LABELS.noValue}</span>
          {onRename && name !== null && (
            <button type="button" className="btn btn--icon btn--quiet" onClick={() => setDraft(name)}
                    aria-label={H.rename(SIDE_LABEL[side])} title={H.renameTitle}>
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
          aria-label={H.nameInput(SIDE_LABEL[side])}
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

/**
 * red: displayed red share in whole percent (blue = 100 - red), null without data.
 * The bar sits on a white inset of the black card, so the red and the blue keep
 * their contrast.
 */
function Momentum({ red, demo, insufficient, excluded }: {
  red: number | null;
  demo: boolean;
  insufficient: boolean;
  excluded: boolean;
}) {
  return (
    <div className="momentum">
      <div className="momentum__label">
        <span className="display">{M.title}</span>
        <HelpTip label={UI_LABELS.help(M.title)} side="bottom">{M.help}</HelpTip>
        <span className="tag tag--muted">{M.experimental}</span>
        {demo && <DemoTag small />}
        {excluded && <span className="tag tag--muted" title={M.excludedHelp}>{M.excluded}</span>}
        {insufficient && !excluded && <span className="tag tag--amber" title={M.insufficientHelp}>{M.insufficient}</span>}
      </div>
      <div className="momentum__bar" role="meter" aria-label={M.meter}
           aria-valuemin={0} aria-valuemax={100} aria-valuenow={red ?? undefined}
           aria-valuetext={red === null ? M.noData : M.shares(red, 100 - red)}>
        <span className="momentum__num momentum__num--red num">{red === null ? UI_LABELS.noValue : `${red}%`}</span>
        <div className="momentum__track">
          {red === null ? <span className="momentum__none" /> : (
            <>
              <span className="momentum__fill momentum__fill--red" style={{ width: `${red}%` }} />
              <span className="momentum__fill momentum__fill--blue" style={{ width: `${100 - red}%` }} />
            </>
          )}
          <span className="momentum__mid" aria-hidden="true" />
        </div>
        <span className="momentum__num momentum__num--blue num">{red === null ? UI_LABELS.noValue : `${100 - red}%`}</span>
      </div>
      <p className="momentum__caption">{M.caption}</p>
    </div>
  );
}

/** Black fighter card: white names, corner labels as red and blue badges, the momentum bar between them. */
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
    <section className="rhead on-ink" aria-label={H.region}>
      <FighterName side="red" name={names?.red ?? null} onRename={actions.onRename} />
      <Momentum red={red} demo={demo} insufficient={insufficient} excluded={excluded} />
      <FighterName side="blue" name={names?.blue ?? null} onRename={actions.onRename} />
      <div className="rhead__actions">
        <button type="button" className="btn btn--ghost btn--sm" onClick={actions.onSwap} disabled={!actions.onSwap}>
          <IconSwap size={16} /> {H.swap}
        </button>
        <button type="button" className="btn btn--ghost btn--sm" onClick={actions.onReselect} disabled={!actions.onReselect}>
          <IconTarget size={16} /> {H.reselect}
        </button>
        {actions.onExport && (
          <button type="button" className="btn btn--ghost btn--sm" onClick={actions.onExport}>
            <IconDownload size={16} /> {H.export}
          </button>
        )}
      </div>
    </section>
  );
}
