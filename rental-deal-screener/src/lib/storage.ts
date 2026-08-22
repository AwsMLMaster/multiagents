import { Deal } from "../types";

const STORAGE_KEY = "rental-deal-screener:deals";

export function loadDeals(): Deal[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveDeals(deals: Deal[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(deals));
  } catch {
    // localStorage unavailable (private browsing, quota, etc.) - fail silently,
    // the app still works for the current session.
  }
}
