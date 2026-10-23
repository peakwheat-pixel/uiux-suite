import { useEffect, useState } from "react";

type Order = { id: string; state: string };

async function fetchOrders(): Promise<Order[]> {
  const response = await fetch("/api/orders");
  if (!response.ok) {
    throw new Error("orders unavailable");
  }
  return response.json();
}

export function OrdersPage() {
  const [rows, setRows] = useState<Order[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    fetchOrders().then((data) => setRows(data));
  }, [filter]);

  const removeOrder = async (id: string) => {
    if (!window.confirm(`Delete order ${id}?`)) return;
    await fetch(`/api/orders/${id}`, { method: "DELETE" });
  };

  return (
    <section data-testid="orders-page">
      <h1>Orders</h1>
      <form onSubmit={(event) => event.preventDefault()}>
        <input data-testid="orders-filter" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <button type="submit">Apply</button>
      </form>
      <table className="orders-table">
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.state}</td>
              <td>
                <button data-testid="remove-order" onClick={() => removeOrder(row.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <progress value={80} max={100} data-testid="orders-progress" />
    </section>
  );
}
