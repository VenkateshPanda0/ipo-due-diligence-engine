import type { EligibilityProgress } from "../types/api";

export function ProgressBar({ label, progress }: { label: string; progress: EligibilityProgress }) {
  const passed = Number(progress.pass_percentage);
  const failed = progress.total_rules ? (progress.failed / progress.total_rules) * 100 : 0;
  const inconclusive = progress.total_rules ? (progress.inconclusive / progress.total_rules) * 100 : 0;

  return (
    <section className="progressBlock">
      <div className="progressMeta">
        <span>{label}</span>
        <span>{progress.passed} / {progress.total_rules} passed</span>
      </div>
      <div className="progressTrack">
        <span className="pass" style={{ width: `${passed}%` }} />
        <span className="fail" style={{ width: `${failed}%` }} />
        <span className="review" style={{ width: `${inconclusive}%` }} />
      </div>
    </section>
  );
}
