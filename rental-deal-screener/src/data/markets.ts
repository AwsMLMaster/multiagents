// Reference data captured from the strategy session. Different sources use
// different definitions/dates/methodologies - revalidate before investing.

export interface VacancyYieldRow {
  market: string;
  grossYieldPct: number;
  vacancyPct: number;
  occupancyPct: number;
  vacancyAdjustedYieldPct: number;
}

export const VACANCY_YIELD_TABLE: VacancyYieldRow[] = [
  { market: "Pittsburgh", grossYieldPct: 7.8, vacancyPct: 6.9, occupancyPct: 93.1, vacancyAdjustedYieldPct: 7.26 },
  { market: "Cleveland", grossYieldPct: 6.96, vacancyPct: 6.4, occupancyPct: 93.6, vacancyAdjustedYieldPct: 6.51 },
  { market: "Rochester", grossYieldPct: 6.82, vacancyPct: 6.6, occupancyPct: 93.4, vacancyAdjustedYieldPct: 6.39 },
  { market: "Memphis", grossYieldPct: 7.12, vacancyPct: 10.6, occupancyPct: 89.4, vacancyAdjustedYieldPct: 6.33 },
  { market: "Detroit", grossYieldPct: 6.79, vacancyPct: 9.6, occupancyPct: 90.4, vacancyAdjustedYieldPct: 6.18 },
  { market: "Indianapolis", grossYieldPct: 6.25, vacancyPct: 6.6, occupancyPct: 93.4, vacancyAdjustedYieldPct: 5.83 },
  { market: "Cincinnati", grossYieldPct: 6.11, vacancyPct: 5.4, occupancyPct: 94.6, vacancyAdjustedYieldPct: 5.79 },
  { market: "St. Louis", grossYieldPct: 6.29, vacancyPct: 8.3, occupancyPct: 91.7, vacancyAdjustedYieldPct: 5.72 },
  { market: "Birmingham", grossYieldPct: 6.61, vacancyPct: 14.3, occupancyPct: 85.7, vacancyAdjustedYieldPct: 5.66 },
  { market: "Buffalo", grossYieldPct: 6.03, vacancyPct: 12.5, occupancyPct: 87.5, vacancyAdjustedYieldPct: 5.25 },
];

export type StarRating = 1 | 1.5 | 2 | 2.5 | 3 | 3.5 | 4 | 4.5 | 5;

export interface MarketShortlistRow {
  market: string;
  cashFlow: StarRating;
  jobs: StarRating;
  educationTenantQuality: StarRating;
  vacancy: StarRating;
  propertyManagementEconomics: StarRating;
  rank: number;
  tier: 1 | 2 | "separate";
  rationale: string;
}

export const MARKET_SHORTLIST: MarketShortlistRow[] = [
  { market: "Indianapolis", cashFlow: 4, jobs: 5, educationTenantQuality: 4, vacancy: 4, propertyManagementEconomics: 5, rank: 1, tier: 1, rationale: "Best overall balance between rental economics, employment base, tenant quality and property management." },
  { market: "Cleveland", cashFlow: 5, jobs: 4, educationTenantQuality: 4, vacancy: 4, propertyManagementEconomics: 5, rank: 2, tier: 1, rationale: "Strongest pure cash-flow candidate; multiple property managers reduce dependence on a single provider. Search should be highly neighborhood-specific." },
  { market: "Pittsburgh", cashFlow: 4, jobs: 4, educationTenantQuality: 5, vacancy: 4, propertyManagementEconomics: 4, rank: 3, tier: 1, rationale: "Strongest quality-tenant/education play - universities, healthcare, technology and established employers." },
  { market: "Cincinnati", cashFlow: 4, jobs: 5, educationTenantQuality: 4, vacancy: 5, propertyManagementEconomics: 4, rank: 4, tier: 2, rationale: "Strong jobs base and low vacancy." },
  { market: "Columbus", cashFlow: 3, jobs: 5, educationTenantQuality: 5, vacancy: 4, propertyManagementEconomics: 4, rank: 5, tier: 2, rationale: "Strong jobs/education, weaker pure cash flow." },
  { market: "St. Louis", cashFlow: 4, jobs: 4, educationTenantQuality: 3, vacancy: 3, propertyManagementEconomics: 4, rank: 6, tier: 2, rationale: "Balanced but weaker on education/vacancy." },
  { market: "Dallas–Fort Worth", cashFlow: 2.5, jobs: 5, educationTenantQuality: 5, vacancy: 2.5, propertyManagementEconomics: 4, rank: 7, tier: "separate", rationale: "Excellent economic depth, but rental economics/vacancy less attractive for this pure-cash-flow strategy. Track separately as an employment/growth play." },
  { market: "Detroit", cashFlow: 5, jobs: 3, educationTenantQuality: 3, vacancy: 2, propertyManagementEconomics: 3, rank: 8, tier: 2, rationale: "High cash flow but weaker jobs/vacancy/education profile." },
  { market: "Memphis", cashFlow: 5, jobs: 3, educationTenantQuality: 2.5, vacancy: 2, propertyManagementEconomics: 3, rank: 9, tier: 2, rationale: "High headline yield offset by high vacancy and weaker tenant quality." },
];

export const TIER_1_MARKETS = ["Indianapolis", "Cleveland", "Pittsburgh"];
export const TIER_2_MARKETS = ["Cincinnati", "Columbus", "St. Louis", "Detroit", "Memphis"];
export const ALL_TARGET_MARKETS = [...TIER_1_MARKETS, ...TIER_2_MARKETS, "Dallas–Fort Worth"];

export interface ManagementPricingExample {
  market: string;
  examples: string[];
}

export const MANAGEMENT_PRICING: ManagementPricingExample[] = [
  {
    market: "Indianapolis",
    examples: [
      "~9%, falling to 8% for 3+ properties",
      "10% for one property, falling to 8% for 3–10 and 7% for 11+",
      "~10%",
      "One provider advertising a $60/month flat management fee",
    ],
  },
  {
    market: "Cleveland",
    examples: [
      "~8% for single-family management",
      "~10%, or 8.5% for volume investors",
      "~10% for 1–3 units, falling to 8% for 4–9 units",
    ],
  },
  {
    market: "Pittsburgh",
    examples: ["Generally ~8–10%, depending on provider and service level"],
  },
];

export const RESEARCH_WORKFLOW = [
  "LandGlide / GIS",
  "Identify house",
  "County assessor",
  "County recorder",
  "Tax records",
  "Foreclosure / court records",
  "Distress verification",
  "Estimate equity",
  "Contact owner",
];

export const FREE_ALTERNATIVE_TOOLS = [
  "County GIS",
  "County Assessor",
  "County Recorder",
  "County Treasurer / Tax Collector",
  "County court / probate records",
  "Public foreclosure notices",
];

export const ZIP_SCREENING_CRITERIA = [
  "Median household income preferably > $60k",
  "Bachelor's degree+ population preferably 30%+",
  "Low unemployment",
  "Stable/growing population",
  "Strong rental demand",
  "Low crime relative to surrounding neighborhoods",
  "Reasonable commute to employment centers",
  "Multiple property managers serving the ZIP",
  "Rental vacancy preferably below 8%",
];

export const TARGET_DEFINITION = {
  discountMinPct: 20,
  discountMaxPct: 30,
  grossYieldMinPct: 9,
  vacancyMaxPct: 8,
  managementMaxPct: 10,
};

export interface SourceLink {
  label: string;
  url: string;
}

export const SOURCES: SourceLink[] = [
  { label: "LandGlide", url: "https://landglide.com/" },
  { label: "PropertyIQ", url: "https://www.propertyiq.app/" },
  { label: "Realtor.com Research", url: "https://www.realtor.com/research/" },
  { label: "Zillow Research", url: "https://www.zillow.com/research/" },
  { label: "U.S. Census Housing Vacancy Survey", url: "https://www.census.gov/housing/hvs/" },
  { label: "Bureau of Labor Statistics", url: "https://www.bls.gov/" },
  { label: "Dallas County foreclosure information", url: "https://www.dallascounty.org/government/county-clerk/recording/foreclosures.php" },
];
