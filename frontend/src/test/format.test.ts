import { describe, expect, it } from "vitest";
import { chargeLabel, formatMinor } from "../format";
import type { Charge } from "../types";

function charge(partial: Partial<Charge>): Charge {
  return {
    id: "ch_test",
    amount: 1000,
    amount_refunded: 0,
    currency: "usd",
    status: "succeeded",
    refunded: false,
    created: 0,
    description: null,
    customer: null,
    ...partial,
  };
}

describe("formatMinor", () => {
  it("renders minor units as dollars", () => {
    expect(formatMinor(15900, "usd")).toBe("$159.00");
    expect(formatMinor(1700, "usd")).toBe("$17.00");
    expect(formatMinor(0, "usd")).toBe("$0.00");
  });
});

describe("chargeLabel", () => {
  it("distinguishes refunds from failed and pending charges", () => {
    expect(chargeLabel(charge({}))).toBe("succeeded");
    expect(chargeLabel(charge({ amount_refunded: 200 }))).toBe("partial refund");
    expect(chargeLabel(charge({ amount: 1500, amount_refunded: 1500, refunded: true }))).toBe("refunded");
    expect(chargeLabel(charge({ status: "failed" }))).toBe("failed");
    expect(chargeLabel(charge({ status: "pending" }))).toBe("pending");
  });
});
