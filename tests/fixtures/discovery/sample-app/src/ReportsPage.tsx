import { useEffect, useState } from "react";

export function ReportsPage() {
  const [started, setStarted] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setStarted(true);
    return () => controller.abort();
  }, []);

  return (
    <section data-testid="reports-page">
      <h1>Reports</h1>
      {started ? <progress max="100" value="40" /> : null}
    </section>
  );
}
