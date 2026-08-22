import { Deal } from "../types";
import { TARGET_DEFINITION } from "../data/markets";

export interface DealMetrics {
  annualRentGross: number | null;
  acquisitionDiscountPct: number | null; // vs. estimated market value
  grossYieldOnPriceP: number | null; // annual rent / asking price
  vacancyAdjustedYieldPct: number | null;
  annualExpenses: number | null;
  annualCashFlow: number | null;
  monthlyCashFlow: number | null;
  cashOnCashReturnPct: number | null;
}

/** Compute a numeric value only if all provided inputs are non-null numbers, else null. */
function compute<T extends unknown[]>(
  inputs: [...{ [K in keyof T]: number | null }],
  fn: (...args: T) => number
): number | null {
  if (inputs.some((v) => v === null || v === undefined || Number.isNaN(v))) return null;
  return fn(...(inputs as unknown as T));
}

export function calculateDealMetrics(deal: Deal): DealMetrics {
  const annualRentGross = compute<[number]>(
    [deal.expectedMonthlyRent],
    (rent) => rent * 12
  );

  const acquisitionDiscountPct = compute<[number, number]>(
    [deal.estMarketValue, deal.askingPrice],
    (marketValue, asking) => (marketValue > 0 ? ((marketValue - asking) / marketValue) * 100 : 0)
  );

  const grossYieldOnPriceP = compute<[number, number]>(
    [annualRentGross, deal.askingPrice],
    (rent, price) => (price > 0 ? (rent / price) * 100 : 0)
  );

  const vacancyAdjustedYieldPct = compute<[number, number]>(
    [grossYieldOnPriceP, deal.marketVacancyPct],
    (yieldPct, vacancyPct) => yieldPct * (1 - vacancyPct / 100)
  );

  const effectiveAnnualRent = compute<[number, number]>(
    [annualRentGross, deal.marketVacancyPct ?? 0],
    (rent, vacancyPct) => rent * (1 - vacancyPct / 100)
  );

  const managementCost = compute<[number, number]>(
    [effectiveAnnualRent, deal.managementFeePct],
    (rent, pct) => rent * (pct / 100)
  );

  const maintenanceCapexCost = compute<[number, number]>(
    [effectiveAnnualRent, deal.maintenanceCapexPct],
    (rent, pct) => rent * (pct / 100)
  );

  const hoaAnnual = deal.hoaMonthly !== null ? deal.hoaMonthly * 12 : null;

  const expenseParts = [
    deal.propertyTaxAnnual,
    deal.insuranceAnnual,
    managementCost,
    maintenanceCapexCost,
    hoaAnnual,
    deal.turnoverCostAnnual,
  ];
  const annualExpenses = expenseParts.every((v) => v !== null && v !== undefined)
    ? (expenseParts as number[]).reduce((a, b) => a + b, 0)
    : null;

  const annualCashFlow = compute<[number, number]>(
    [effectiveAnnualRent, annualExpenses],
    (rent, expenses) => rent - expenses
  );

  const monthlyCashFlow = annualCashFlow !== null ? annualCashFlow / 12 : null;

  const cashOnCashReturnPct = compute<[number, number]>(
    [annualCashFlow, deal.estimatedTotalCashRequired],
    (cf, cash) => (cash > 0 ? (cf / cash) * 100 : 0)
  );

  return {
    annualRentGross,
    acquisitionDiscountPct,
    grossYieldOnPriceP,
    vacancyAdjustedYieldPct,
    annualExpenses,
    annualCashFlow,
    monthlyCashFlow,
    cashOnCashReturnPct,
  };
}

export interface TargetCheck {
  label: string;
  pass: boolean | null; // null = insufficient data
  detail: string;
}

export function checkAgainstTargets(deal: Deal, metrics: DealMetrics): TargetCheck[] {
  const checks: TargetCheck[] = [];

  checks.push({
    label: `Discount ${TARGET_DEFINITION.discountMinPct}–${TARGET_DEFINITION.discountMaxPct}% below market value`,
    pass: metrics.acquisitionDiscountPct === null ? null : metrics.acquisitionDiscountPct >= TARGET_DEFINITION.discountMinPct,
    detail: metrics.acquisitionDiscountPct === null ? "Enter market value & asking price" : `${metrics.acquisitionDiscountPct.toFixed(1)}% below market value`,
  });

  checks.push({
    label: `Gross yield ≥ ${TARGET_DEFINITION.grossYieldMinPct}%`,
    pass: metrics.grossYieldOnPriceP === null ? null : metrics.grossYieldOnPriceP >= TARGET_DEFINITION.grossYieldMinPct,
    detail: metrics.grossYieldOnPriceP === null ? "Enter rent & asking price" : `${metrics.grossYieldOnPriceP.toFixed(2)}% gross yield`,
  });

  checks.push({
    label: `Market vacancy < ${TARGET_DEFINITION.vacancyMaxPct}%`,
    pass: deal.marketVacancyPct === null ? null : deal.marketVacancyPct < TARGET_DEFINITION.vacancyMaxPct,
    detail: deal.marketVacancyPct === null ? "Enter market vacancy %" : `${deal.marketVacancyPct}% vacancy`,
  });

  checks.push({
    label: `Property management ≤ ${TARGET_DEFINITION.managementMaxPct}%`,
    pass: deal.managementFeePct === null ? null : deal.managementFeePct <= TARGET_DEFINITION.managementMaxPct,
    detail: deal.managementFeePct === null ? "Enter management fee %" : `${deal.managementFeePct}% management fee`,
  });

  checks.push({
    label: "Positive net cash flow",
    pass: metrics.monthlyCashFlow === null ? null : metrics.monthlyCashFlow > 0,
    detail: metrics.monthlyCashFlow === null ? "Fill in income & expenses" : `$${metrics.monthlyCashFlow.toFixed(0)}/mo net cash flow`,
  });

  return checks;
}

export function formatCurrency(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export function formatPercent(value: number | null, digits = 1): string {
  if (value === null || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}%`;
}
