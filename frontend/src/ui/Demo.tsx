import { DEMO_LABELS } from "../labels";
import { cx } from "./cx";

/** Permanent strip under the top bar in Demo mode: nothing shown is a real analysis. */
export function DemoBanner() {
  return (
    <div className="demo-banner" role="note">
      <span className="demo-banner__tag">{DEMO_LABELS.tag}</span>
      <span>{DEMO_LABELS.banner}</span>
    </div>
  );
}

export function DemoTag({ small = false }: { small?: boolean }) {
  return <span className={cx("demo-tag", small && "demo-tag--small")}>{DEMO_LABELS.tag}</span>;
}
