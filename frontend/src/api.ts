export const currencies = ["USD", "EUR", "GBP", "INR", "AUD", "CAD", "JPY"] as const;

export type Currency = (typeof currencies)[number];
export type TransactionKind = "credit" | "debit" | "transfer_out" | "transfer_in";

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Profile {
  id: number;
  email: string;
  display_name: string;
  photo_url: string | null;
  default_currency: Currency;
  created_at: string;
}

export interface Wallet {
  id: number;
  currency: Currency;
  balance: string;
  version: number;
  updated_at: string;
}

export interface WalletTransaction {
  id: number;
  kind: TransactionKind;
  status: string;
  amount: string;
  currency: Currency;
  wallet_currency: Currency;
  wallet_amount: string;
  exchange_rate_value: string;
  exchange_provider: string;
  exchange_fetched_at: string;
  counterparty_id: number | null;
  related_transaction_id: number | null;
  description: string | null;
  created_at: string;
}

export interface TransactionPage {
  items: WalletTransaction[];
  page: number;
  page_size: number;
  total: number;
}

export interface Rate {
  currency: Currency;
  rate: string;
  provider: string;
  fetched_at: string;
}

export interface Quote {
  source_amount: string;
  source_currency: Currency;
  target_amount: string;
  target_currency: Currency;
  exchange_rate_value: string;
  provider: string;
  fetched_at: string;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function detailToMessage(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (isRecord(item) && typeof item.msg === "string") {
          return item.msg;
        }
        return "Validation error";
      })
      .join(", ");
  }
  return "Request failed";
}

export async function apiRequest<T>(path: string, token: string | null, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (isRecord(payload) && "detail" in payload) {
      throw new Error(detailToMessage(payload.detail));
    }
    throw new Error(`Request failed with status ${response.status}`);
  }
  return payload as T;
}

export function money(value: string | number, currency: Currency): string {
  return new Intl.NumberFormat("en-GB", { style: "currency", currency }).format(Number(value));
}

export function compactDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
