import { FormEvent, useState } from "react";
import { useRouter } from "next/router";
import { ipoApi } from "../services/api";

export default function UploadPage() {
  const router = useRouter();
  const [jsonInput, setJsonInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  async function submitJson(event: FormEvent) {
    event.preventDefault();
    setIsBusy(true);
    setError(null);
    try {
      let payload: unknown;
      try {
        payload = JSON.parse(jsonInput);
      } catch {
        throw new Error("Invalid JSON. Check commas, quotes, and braces.");
      }
      const report = await ipoApi.screenJSON(payload);
      await router.push(`/report/${report.report_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Screening failed");
    } finally {
      setIsBusy(false);
    }
  }

  async function submitFile(file: File | undefined) {
    if (!file) return;
    setIsBusy(true);
    setError(null);
    try {
      const report = await ipoApi.screenPDF(file);
      await router.push(`/report/${report.report_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <main className="shell">
      <form className="panel" onSubmit={submitJson}>
        <h1>IPO Due Diligence Engine</h1>
        <textarea
          aria-label="CompanyData JSON"
          value={jsonInput}
          onChange={(event) => setJsonInput(event.target.value)}
        />
        <div className="actions">
          <input
            aria-label="Upload PDF"
            type="file"
            accept="application/pdf"
            onChange={(event) => void submitFile(event.target.files?.[0])}
          />
          <button disabled={isBusy || !jsonInput.trim()} type="submit">{isBusy ? "Processing" : "Screen JSON"}</button>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </form>
    </main>
  );
}
