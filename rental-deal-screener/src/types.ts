export type DistressSignal =
  | "Pre-foreclosure / Notice of Default"
  | "Property-tax delinquency"
  | "Tax lien"
  | "Lis pendens"
  | "Foreclosure"
  | "Code violations"
  | "Probate / inherited property"
  | "Absentee owner"
  | "Long ownership period"
  | "Recorded liens/judgments";

export const DISTRESS_SIGNALS: DistressSignal[] = [
  "Pre-foreclosure / Notice of Default",
  "Property-tax delinquency",
  "Tax lien",
  "Lis pendens",
  "Foreclosure",
  "Code violations",
  "Probate / inherited property",
  "Absentee owner",
  "Long ownership period",
  "Recorded liens/judgments",
];

export type PopulationTrend = "Growing" | "Stable" | "Declining" | "Unknown";

export interface Deal {
  id: string;
  createdAt: string;
  updatedAt: string;

  // Identification
  address: string;
  market: string;
  zip: string;
  propertyType: string;

  // Valuation & acquisition
  estMarketValue: number | null;
  askingPrice: number | null;
  distressSignals: DistressSignal[];

  // Rental income
  expectedMonthlyRent: number | null;
  marketVacancyPct: number | null; // e.g. 6.9 for 6.9%

  // Operating expenses (annual unless noted)
  propertyTaxAnnual: number | null;
  insuranceAnnual: number | null;
  managementFeePct: number | null; // % of collected rent
  maintenanceCapexPct: number | null; // % of collected rent, combined maintenance+CapEx reserve
  hoaMonthly: number | null;
  turnoverCostAnnual: number | null;

  // Cash required
  estimatedTotalCashRequired: number | null;

  // Neighborhood screening criteria
  neighborhoodMedianIncome: number | null;
  bachelorsPlusPct: number | null;
  unemploymentPct: number | null;
  populationTrend: PopulationTrend;
  crimeNote: string;
  commuteNote: string;
  propertyManagerOptions: string;

  notes: string;
}

export function emptyDeal(): Deal {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    createdAt: now,
    updatedAt: now,
    address: "",
    market: "",
    zip: "",
    propertyType: "Single-family",
    estMarketValue: null,
    askingPrice: null,
    distressSignals: [],
    expectedMonthlyRent: null,
    marketVacancyPct: null,
    propertyTaxAnnual: null,
    insuranceAnnual: null,
    managementFeePct: null,
    maintenanceCapexPct: null,
    hoaMonthly: null,
    turnoverCostAnnual: null,
    estimatedTotalCashRequired: null,
    neighborhoodMedianIncome: null,
    bachelorsPlusPct: null,
    unemploymentPct: null,
    populationTrend: "Unknown",
    crimeNote: "",
    commuteNote: "",
    propertyManagerOptions: "",
    notes: "",
  };
}
