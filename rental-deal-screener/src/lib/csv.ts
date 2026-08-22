import { Deal } from "../types";
import { calculateDealMetrics } from "./calculations";

const COLUMNS: Array<{ header: string; get: (d: Deal) => string | number }> = [
  { header: "Address", get: (d) => d.address },
  { header: "Market", get: (d) => d.market },
  { header: "ZIP", get: (d) => d.zip },
  { header: "Property Type", get: (d) => d.propertyType },
  { header: "Est. Market Value", get: (d) => d.estMarketValue ?? "" },
  { header: "Asking Price", get: (d) => d.askingPrice ?? "" },
  { header: "Distress Signals", get: (d) => d.distressSignals.join("; ") },
  { header: "Expected Monthly Rent", get: (d) => d.expectedMonthlyRent ?? "" },
  { header: "Market Vacancy %", get: (d) => d.marketVacancyPct ?? "" },
  { header: "Property Tax (annual)", get: (d) => d.propertyTaxAnnual ?? "" },
  { header: "Insurance (annual)", get: (d) => d.insuranceAnnual ?? "" },
  { header: "Management Fee %", get: (d) => d.managementFeePct ?? "" },
  { header: "Maintenance/CapEx %", get: (d) => d.maintenanceCapexPct ?? "" },
  { header: "HOA (monthly)", get: (d) => d.hoaMonthly ?? "" },
  { header: "Turnover Cost (annual)", get: (d) => d.turnoverCostAnnual ?? "" },
  { header: "Est. Total Cash Required", get: (d) => d.estimatedTotalCashRequired ?? "" },
  { header: "Acquisition Discount %", get: (d) => calculateDealMetrics(d).acquisitionDiscountPct?.toFixed(1) ?? "" },
  { header: "Gross Yield %", get: (d) => calculateDealMetrics(d).grossYieldOnPriceP?.toFixed(2) ?? "" },
  { header: "Vacancy-Adjusted Yield %", get: (d) => calculateDealMetrics(d).vacancyAdjustedYieldPct?.toFixed(2) ?? "" },
  { header: "Net Monthly Cash Flow", get: (d) => calculateDealMetrics(d).monthlyCashFlow?.toFixed(0) ?? "" },
  { header: "Cash-on-Cash Return %", get: (d) => calculateDealMetrics(d).cashOnCashReturnPct?.toFixed(1) ?? "" },
  { header: "Neighborhood Median Income", get: (d) => d.neighborhoodMedianIncome ?? "" },
  { header: "Bachelor's+ %", get: (d) => d.bachelorsPlusPct ?? "" },
  { header: "Unemployment %", get: (d) => d.unemploymentPct ?? "" },
  { header: "Population Trend", get: (d) => d.populationTrend },
  { header: "Crime Note", get: (d) => d.crimeNote },
  { header: "Commute Note", get: (d) => d.commuteNote },
  { header: "Property Manager Options", get: (d) => d.propertyManagerOptions },
  { header: "Notes", get: (d) => d.notes },
];

function escapeCsvValue(value: string | number): string {
  const str = String(value ?? "");
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function dealsToCsv(deals: Deal[]): string {
  const header = COLUMNS.map((c) => escapeCsvValue(c.header)).join(",");
  const rows = deals.map((d) => COLUMNS.map((c) => escapeCsvValue(c.get(d))).join(","));
  return [header, ...rows].join("\n");
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
