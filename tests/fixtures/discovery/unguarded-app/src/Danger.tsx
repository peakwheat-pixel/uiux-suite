export function DangerPage() {
  const purgeAll = async () => {
    await fetch("/api/purge", { method: "POST" });
  };

  return (
    <section data-testid="danger-page">
      <button data-testid="purge-all" onClick={purgeAll}>Purge all records</button>
    </section>
  );
}
