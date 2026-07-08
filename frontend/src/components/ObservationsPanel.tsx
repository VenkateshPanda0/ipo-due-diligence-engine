export function ObservationsPanel({ observations }: { observations: string[] }) {
  return (
    <section>
      <h2>Observations</h2>
      {observations.length === 0 ? <p className="muted">No additional observations.</p> : null}
      <ul>{observations.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );
}
