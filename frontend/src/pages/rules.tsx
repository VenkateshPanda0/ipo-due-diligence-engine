import { useEffect, useMemo, useState } from "react";
import { RuleList } from "../components/RuleList";
import { ipoApi } from "../services/api";
import type { RuleDetail } from "../types/api";

export default function RulesPage() {
  const [rules, setRules] = useState<RuleDetail[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<"all" | "mandatory" | "advisory">("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    ipoApi
      .getRules(category === "all" ? undefined : category)
      .then((response) => {
        setRules(response.rules);
      })
      .catch((err: Error) => {
        setRules([]);
        setError(err.message);
      });
  }, [category]);

  const filtered = useMemo(
    () => rules.filter((rule) => `${rule.rule_id} ${rule.regulation_reference}`.toLowerCase().includes(query.toLowerCase())),
    [query, rules],
  );

  return (
    <main className="shell">
      <section className="toolbar">
        <h1>Rule Explorer</h1>
        <input value={query} onChange={(event) => setQuery(event.target.value)} />
        <select value={category} onChange={(event) => setCategory(event.target.value as typeof category)}>
          <option value="all">All</option>
          <option value="mandatory">Mandatory</option>
          <option value="advisory">Advisory</option>
        </select>
      </section>
      {error ? <p className="error">{error}</p> : null}
      <RuleList rules={filtered} />
    </main>
  );
}
