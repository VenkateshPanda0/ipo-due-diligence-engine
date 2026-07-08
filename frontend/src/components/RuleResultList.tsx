import type { RuleResult } from "../types/api";
import { EvidencePanel } from "./EvidencePanel";

const verdictLabel = {
  pass: "PASS",
  fail: "FAIL",
  inconclusive: "REVIEW",
};

export function RuleResultList({ title, results }: { title: string; results: RuleResult[] }) {
  return (
    <section>
      <h2>{title}</h2>
      <div className="resultList">
        {results.map((result) => (
          <details key={result.rule_id} className={`result ${result.verdict}`}>
            <summary>
              <span>{verdictLabel[result.verdict]}</span>
              <strong>{result.rule_id}</strong>
              <em>{result.regulation_reference}</em>
            </summary>
            <p>{result.description}</p>
            <dl>
              <dt>Required</dt><dd>{result.required_value}</dd>
              <dt>Actual</dt><dd>{result.actual_value ?? "Unavailable"}</dd>
              {result.gap ? <><dt>Gap</dt><dd>{result.gap}</dd></> : null}
              <dt>Evidence</dt><dd><EvidencePanel citation={result.source_citation} /></dd>
            </dl>
            <p>{result.explanation}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
