import type { GapAnalysisItem } from "../types/api";

export function GapPlanner({ gaps }: { gaps: GapAnalysisItem[] }) {
  return (
    <section>
      <h2>Gap Planner</h2>
      {gaps.length === 0 ? <p className="muted">No failed mandatory requirements.</p> : null}
      {gaps.map((gap) => (
        <article className="gap" key={gap.rule_id}>
          <h3>{gap.rule_id}</h3>
          <p>{gap.gap_size}</p>
          <p>{gap.current_value} vs {gap.required_value}</p>
          <strong>{gap.earliest_eligible_fy}</strong>
          <ul>{gap.remediation_steps.map((step) => <li key={step}>{step}</li>)}</ul>
        </article>
      ))}
    </section>
  );
}
