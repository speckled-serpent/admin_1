import type { Charge } from "./types";

/** Display money that the API reports in minor units. Assumes 2 decimal places. */
export function formatMinor(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(amount / 100);
}

export function formatUnix(seconds: number): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(seconds * 1000));
}

export function chargeLabel(charge: Charge): string {
  if (charge.status === "failed") {
    return "failed";
  }
  if (charge.status === "pending") {
    return "pending";
  }
  if (charge.refunded || (charge.amount > 0 && charge.amount_refunded === charge.amount)) {
    return "refunded";
  }
  if (charge.amount_refunded > 0) {
    return "partial refund";
  }
  return "succeeded";
}
