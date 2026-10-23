export function OrdersTable({ rows }: { rows: Row[] }) {
  if (state === "loading") return <div data-state="loading">Loading</div>;
  if (rows.length === 0) return <div data-state="empty">No orders</div>;
  if (state === "error") return <div data-state="error">Retry</div>;
  return <table data-state="ready">{rows.map((row) => <tr key={row.id}>{row.id}</tr>)}</table>;
}

export function OrderToolbar() {
  return <button data-state="ready">Delete</button>;
}
