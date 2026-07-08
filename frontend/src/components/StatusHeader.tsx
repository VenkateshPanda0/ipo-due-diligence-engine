import type { ScreeningResponse } from "../types/api";

const statusLabel = {
  eligible: "Eligible",
  not_eligible: "Not Eligible",
  needs_review: "Needs Review",
};

export function StatusHeader({ report }: { report: ScreeningResponse }) {
  return (
    <header className={`statusHeader ${report.status}`}>
      <div>
        <h1>{report.company_name}</h1>
        <p>
          Ruleset {report.ruleset_version} | {new Date(report.evaluated_at).toLocaleString()}
        </p>
        <p className="muted">Machine screening only. Decision authority: {report.decision_authority}.</p>
      </div>
      <strong>{statusLabel[report.status]}</strong>
    </header>
  );
}
