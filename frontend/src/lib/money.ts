/**
 * Money formatting and display helpers.
 *
 * The backend already renders every amount (`Money.formatted`), so the default
 * path is simply to show that string. These helpers exist for the two cases
 * the backend cannot cover:
 *
 *   - formatting a *sum* computed in the UI from several server amounts;
 *   - the price slider, whose bounds are raw minor units from the facets
 *     endpoint and must be shown as rupee values.
 *
 * Indian digit grouping is applied here for that second case: 1234567 must
 * read as "12,34,567", not "1,234,567".
 */

import type { Money } from "./api/types";

/** Group a digit string using the Indian lakh/crore convention. */
function groupIndian(digits: string): string {
  if (digits.length <= 3) return digits;
  const head = digits.slice(0, -3);
  const tail = digits.slice(-3);
  if (head.length <= 2) return `${head},${tail}`;
  const groups: string[] = [];
  let rest = head;
  while (rest.length > 2) {
    groups.unshift(rest.slice(-2));
    rest = rest.slice(0, -2);
  }
  groups.unshift(rest);
  return `${groups.join(",")},${tail}`;
}

/**
 * Format minor units for display. Integer arithmetic only — a float here would
 * make `Rs.1,234.50` sometimes render as `Rs.1,234.49`.
 */
export function formatMinor(amount: number, symbol = "Rs."): string {
  const sign = amount < 0 ? "-" : "";
  const abs = Math.abs(Math.trunc(amount));
  const rupees = Math.floor(abs / 100);
  const paise = abs % 100;
  const whole = groupIndian(String(rupees));
  return paise > 0
    ? `${sign}${symbol}${whole}.${String(paise).padStart(2, "0")}`
    : `${sign}${symbol}${whole}`;
}

/** The server's own string, which is authoritative. */
export function moneyLabel(money: Money | null | undefined): string {
  return money?.formatted ?? "";
}

/** Compact form for dense UI: Rs.1.2L / Rs.24,990. */
export function formatCompactMinor(amount: number, symbol = "Rs."): string {
  if (amount >= 10_000_00) {
    return `${symbol}${(amount / 10_000_00).toFixed(amount % 10_000_00 === 0 ? 0 : 1)} Cr`;
  }
  if (amount >= 1_00_000) {
    return `${symbol}${(amount / 1_00_000).toFixed(amount % 1_00_000 === 0 ? 0 : 1)} L`;
  }
  if (amount >= 1_000) {
    return `${symbol}${(amount / 1_000).toFixed(amount % 1_000 === 0 ? 0 : 1)}K`;
  }
  return `${symbol}${Math.trunc(amount / 100)}`;
}

/** Sum of server-rendered amounts, then format. Display only. */
export function sumMoney(amounts: number[], symbol = "Rs."): string {
  return formatMinor(amounts.reduce((total, value) => total + value, 0), symbol);
}

/** Label for a stock status, tuned per status rather than a generic string. */
export function stockLabel(status: string): string {
  switch (status) {
    case "in_stock":
      return "In stock";
    case "low_stock":
      return "Low stock";
    case "out_of_stock":
      return "Out of stock";
    case "preorder":
      return "On order";
    default:
      return "Availability on request";
  }
}

export function stockTone(
  status: string,
): "ok" | "warn" | "danger" | "muted" {
  switch (status) {
    case "in_stock":
      return "ok";
    case "low_stock":
      return "warn";
    case "out_of_stock":
      return "danger";
    default:
      return "muted";
  }
}

/**
 * Ratings are only rendered when real data backs them.
 *
 * The seeded catalogue ships with zero reviews because the live site publishes
 * none, and an invented star rating is worse than an honest "no reviews yet".
 * This is the single place that decision is enforced in the UI.
 */
export function hasRealRating(count: number): boolean {
  return count > 0;
}
