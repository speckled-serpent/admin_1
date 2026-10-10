import { chargeLabel, formatMinor, formatUnix } from "../format";
import type { Revenue } from "../types";

export function RevenueView({ revenue }: { revenue: Revenue }) {
  const currency = revenue.currency ?? "usd";
  return (
    <div className="revenue-view">
      <p className="lede">Local revenue for this project. Captured charges, refunds, and what remains.</p>
      <section className="stats" aria-label="Revenue totals">
        <article className="stat" aria-label="Gross">
          <p className="stat-label">Gross</p>
          <p className="stat-value">{formatMinor(revenue.gross_amount, currency)}</p>
          <p className="stat-note">{revenue.succeeded_count} succeeded charges</p>
        </article>
        <article className="stat" aria-label="Refunded">
          <p className="stat-label">Refunded</p>
          <p className="stat-value refund">{formatMinor(revenue.refunded_amount, currency)}</p>
          <p className="stat-note">{revenue.refunded_count} with a refund</p>
        </article>
        <article className="stat" aria-label="Net">
          <p className="stat-label">Net</p>
          <p className="stat-value">{formatMinor(revenue.net_amount, currency)}</p>
          <p className="stat-note">{revenue.charge_count} charges in the fixture</p>
        </article>
      </section>
      <section className="panel">
        <div className="panel-head">
          <h2>Charges</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Description</th>
                <th>Status</th>
                <th className="num">Amount</th>
                <th className="num">Refunded</th>
              </tr>
            </thead>
            <tbody>
              {revenue.charges.map((charge) => (
                <tr key={charge.id}>
                  <td>{formatUnix(charge.created)}</td>
                  <td>
                    <div>{charge.description ?? charge.id}</div>
                    {charge.customer ? <div className="cell-sub">{charge.customer}</div> : null}
                  </td>
                  <td>
                    <span className={`pill pill-${chargeLabel(charge).replace(" ", "-")}`}>{chargeLabel(charge)}</span>
                  </td>
                  <td className="num">{formatMinor(charge.amount, charge.currency)}</td>
                  <td className="num">
                    {charge.amount_refunded > 0 ? formatMinor(charge.amount_refunded, charge.currency) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
