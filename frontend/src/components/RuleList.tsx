import type { RuleDetail } from "../types/api";

export function RuleList({ rules }: { rules: RuleDetail[] }) {
  return (
    <table className="rules">
      <thead>
        <tr><th>Rule</th><th>Category</th><th>Regulation</th><th>Threshold</th></tr>
      </thead>
      <tbody>
        {rules.map((rule) => (
          <tr key={rule.rule_id}>
            <td>{rule.rule_id}</td>
            <td>{rule.category}</td>
            <td>{rule.regulation_reference}</td>
            <td>{rule.threshold}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
