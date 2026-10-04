import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/router";
import { useState, type FormEvent } from "react";
import { AppShell, PageHead } from "@/components/layout/AppShell";
import { Card, ErrorState, Field, Notice } from "@/components/ui";
import { api } from "@/lib/api";
import { ROUTES, validateCaseForm } from "@/lib/forms";

export default function NewCasePage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [route, setRoute] = useState<string>("mainboard_reg6_1");
  const [notes, setNotes] = useState("");
  const [touched, setTouched] = useState(false);
  const nameError = validateCaseForm(name);
  const create = useMutation({
    mutationFn: () => api.createCase({ company_name: name.trim(), listing_route: route, notes: notes.trim() || undefined }),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["cases"] });
      router.push(`/cases/${c.id}?tab=documents`);
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!nameError) create.mutate();
  }

  return (
    <AppShell title="New screening case">
      <PageHead title="New screening case" description="Step 1 of 4 — company details and intended listing route." />
      <ol className="steps" aria-label="Workflow steps" style={{ marginBottom: 18 }}>
        <li data-state="current">1. Company &amp; route</li>
        <li>2. Upload documents</li>
        <li>3. Review evidence</li>
        <li>4. Run screening</li>
      </ol>
      <form onSubmit={submit} noValidate>
        <Card title="Company">
          <div className="stack" style={{ maxWidth: 640 }}>
            <Field label="Company name" required error={touched ? nameError : null} hint="Registered name as it appears in the offer document.">
              <input value={name} onChange={(e) => setName(e.target.value)} onBlur={() => setTouched(true)} aria-invalid={touched && !!nameError} maxLength={300} autoFocus />
            </Field>
            <fieldset>
              <legend>Intended listing route</legend>
              <div className="stack">
                {ROUTES.map((r) => (
                  <label key={r.id} className="radio-card">
                    <input type="radio" name="route" value={r.id} checked={route === r.id} onChange={() => setRoute(r.id)} />
                    <span>
                      <strong>{r.title}</strong>
                      <br />
                      <span className="muted">{r.body}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            {route === "sme_chapter_ix" && (
              <Notice tone="caution" title="Unsupported route">
                The SME route is not implemented. Screening will report &ldquo;unsupported regulatory scope&rdquo; rather than any
                pass/fail result.
              </Notice>
            )}
            <Field label="Internal notes" hint="Visible to everyone with access to this case.">
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={5000} />
            </Field>
          </div>
        </Card>
        {create.isError && (
          <div style={{ marginTop: 16 }}>
            <ErrorState error={create.error} />
          </div>
        )}
        <div className="row" style={{ marginTop: 16 }}>
          <button className="btn btn-primary" type="submit" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create case and continue"}
          </button>
          <button className="btn" type="button" onClick={() => router.back()}>
            Cancel
          </button>
        </div>
      </form>
    </AppShell>
  );
}
