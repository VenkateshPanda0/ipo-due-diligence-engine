import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { GapPlanner } from "../../components/GapPlanner";
import { HumanReviewPanel } from "../../components/HumanReviewPanel";
import { ObservationsPanel } from "../../components/ObservationsPanel";
import { ProgressBar } from "../../components/ProgressBar";
import { RuleResultList } from "../../components/RuleResultList";
import { StatusHeader } from "../../components/StatusHeader";
import { ipoApi } from "../../services/api";
import type { ScreeningResponse } from "../../types/api";

export default function ReportPage() {
  const router = useRouter();
  const [report, setReport] = useState<ScreeningResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = router.query.id;
    if (typeof id !== "string") return;
    ipoApi.getReport(id).then(setReport).catch((err: Error) => setError(err.message));
  }, [router.query.id]);

  if (error) return <main className="shell"><p className="error">{error}</p></main>;
  if (!report) return <main className="shell"><p>Loading</p></main>;

  return (
    <main className="shell">
      <StatusHeader report={report} />
      <HumanReviewPanel report={report} />
      <ProgressBar label="Mandatory" progress={report.mandatory_progress} />
      <ProgressBar label="Advisory" progress={report.advisory_progress} />
      <RuleResultList title="Mandatory Requirements" results={report.mandatory_results} />
      <RuleResultList title="Advisory Checks" results={report.advisory_results} />
      <GapPlanner gaps={report.gap_analysis} />
      <ObservationsPanel observations={report.observations} />
    </main>
  );
}
