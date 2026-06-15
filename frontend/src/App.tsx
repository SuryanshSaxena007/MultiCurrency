import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Currency,
  Profile,
  Quote,
  Rate,
  TokenResponse,
  TransactionKind,
  TransactionPage,
  Wallet,
  WalletTransaction,
  apiRequest,
  compactDate,
  currencies,
  money,
} from "./api";

const kinds: Array<TransactionKind | ""> = ["", "credit", "debit", "transfer_out", "transfer_in"];

interface AuthForm {
  email: string;
  password: string;
  display_name: string;
  default_currency: Currency;
  photo_url: string;
}

interface ProfileForm {
  display_name: string;
  default_currency: Currency;
  photo_url: string;
}

interface MoneyForm {
  amount: string;
  currency: Currency;
  wallet_currency: Currency;
  description: string;
  idempotency_key: string;
}

interface TransferForm {
  recipient_email: string;
  amount: string;
  currency: Currency;
  source_wallet_currency: Currency;
  target_wallet_currency: Currency;
  description: string;
  idempotency_key: string;
}

interface HistoryFilter {
  kind: TransactionKind | "";
  currency: Currency | "";
  page: number;
}

const initialAuth: AuthForm = {
  email: "",
  password: "",
  display_name: "",
  default_currency: "USD",
  photo_url: "",
};

const initialMoney: MoneyForm = {
  amount: "25.00",
  currency: "USD",
  wallet_currency: "USD",
  description: "",
  idempotency_key: "",
};

const initialTransfer: TransferForm = {
  recipient_email: "",
  amount: "10.00",
  currency: "USD",
  source_wallet_currency: "USD",
  target_wallet_currency: "EUR",
  description: "",
  idempotency_key: "",
};

function App() {
  const [token, setToken] = useState(() => localStorage.getItem("wallet_token"));
  const [authMode, setAuthMode] = useState<"login" | "signup">("signup");
  const [authForm, setAuthForm] = useState<AuthForm>(initialAuth);
  const [profileForm, setProfileForm] = useState<ProfileForm>({ display_name: "", default_currency: "USD", photo_url: "" });
  const [moneyForm, setMoneyForm] = useState<MoneyForm>(initialMoney);
  const [transferForm, setTransferForm] = useState<TransferForm>(initialTransfer);
  const [historyFilter, setHistoryFilter] = useState<HistoryFilter>({ kind: "", currency: "", page: 1 });
  const [quoteForm, setQuoteForm] = useState({ amount: "100.00", source_currency: "USD" as Currency, target_currency: "EUR" as Currency });
  const [profile, setProfile] = useState<Profile | null>(null);
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [transactions, setTransactions] = useState<TransactionPage>({ items: [], page: 1, page_size: 10, total: 0 });
  const [rates, setRates] = useState<Rate[]>([]);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const signedIn = Boolean(token);
  const defaultCurrencyTotal = useMemo(() => {
    if (!profile) {
      return 0;
    }
    const usdRates = new Map(rates.map((rate) => [rate.currency, Number(rate.rate)]));
    const targetRate = usdRates.get(profile.default_currency);
    if (!targetRate) {
      return 0;
    }
    return wallets.reduce((sum, wallet) => {
      const sourceRate = usdRates.get(wallet.currency);
      if (!sourceRate) {
        return sum;
      }
      return sum + (Number(wallet.balance) / sourceRate) * targetRate;
    }, 0);
  }, [profile, rates, wallets]);

  const showError = (value: unknown) => {
    setError(value instanceof Error ? value.message : "Unexpected error");
    setMessage(null);
  };

  const clearSession = (notice: string) => {
    localStorage.removeItem("wallet_token");
    setToken(null);
    setProfile(null);
    setWallets([]);
    setTransactions({ items: [], page: 1, page_size: 10, total: 0 });
    setRates([]);
    setMessage(notice);
  };

  const loadDashboard = useCallback(async () => {
    if (!token) {
      return;
    }
    const [profileResult, walletResult, transactionResult, rateResult] = await Promise.all([
      apiRequest<Profile>("/profile", token),
      apiRequest<Wallet[]>("/wallets", token),
      apiRequest<TransactionPage>(
        `/transactions?page=${historyFilter.page}&page_size=10${historyFilter.kind ? `&kind=${historyFilter.kind}` : ""}${
          historyFilter.currency ? `&currency=${historyFilter.currency}` : ""
        }`,
        token,
      ),
      apiRequest<Rate[]>("/exchange/rates", token),
    ]);
    setProfile(profileResult);
    setWallets(walletResult);
    setTransactions(transactionResult);
    setRates(rateResult);
    setProfileForm({
      display_name: profileResult.display_name,
      default_currency: profileResult.default_currency,
      photo_url: profileResult.photo_url || "",
    });
  }, [historyFilter.currency, historyFilter.kind, historyFilter.page, token]);

  useEffect(() => {
    if (!token) {
      return;
    }
    loadDashboard().catch((caught: unknown) => {
      if (caught instanceof Error && caught.message === "Invalid credentials") {
        clearSession("Session expired. Please sign in again.");
        setError(null);
        return;
      }
      showError(caught);
    });
  }, [loadDashboard, token]);

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const path = authMode === "signup" ? "/auth/signup" : "/auth/login";
      const body =
        authMode === "signup"
          ? authForm
          : {
              email: authForm.email,
              password: authForm.password,
            };
      const result = await apiRequest<TokenResponse>(path, null, { method: "POST", body: JSON.stringify(body) });
      localStorage.setItem("wallet_token", result.access_token);
      setToken(result.access_token);
      setMessage(authMode === "signup" ? "Account created" : "Signed in");
    } catch (caught) {
      showError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function updateProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await apiRequest<Profile>("/profile", token, {
        method: "PATCH",
        body: JSON.stringify(profileForm),
      });
      setProfile(result);
      await loadDashboard();
      setMessage("Profile updated");
      setError(null);
    } catch (caught) {
      showError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function postMoney(path: "/wallets/credit" | "/wallets/debit") {
    setBusy(true);
    try {
      await apiRequest<WalletTransaction>(path, token, {
        method: "POST",
        body: JSON.stringify({
          amount: moneyForm.amount,
          currency: moneyForm.currency,
          wallet_currency: moneyForm.wallet_currency,
          description: moneyForm.description || null,
          idempotency_key: moneyForm.idempotency_key || null,
        }),
      });
      await loadDashboard();
      setMessage(path.endsWith("credit") ? "Wallet credited" : "Wallet debited");
      setError(null);
    } catch (caught) {
      showError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function submitTransfer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      await apiRequest<WalletTransaction>("/transfers", token, {
        method: "POST",
        body: JSON.stringify({
          recipient_email: transferForm.recipient_email,
          amount: transferForm.amount,
          currency: transferForm.currency,
          source_wallet_currency: transferForm.source_wallet_currency,
          target_wallet_currency: transferForm.target_wallet_currency,
          description: transferForm.description || null,
          idempotency_key: transferForm.idempotency_key || null,
        }),
      });
      await loadDashboard();
      setMessage("Transfer posted atomically");
      setError(null);
    } catch (caught) {
      showError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function fetchQuote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await apiRequest<Quote>(
        `/exchange/quote?amount=${quoteForm.amount}&source_currency=${quoteForm.source_currency}&target_currency=${quoteForm.target_currency}`,
        token,
      );
      setQuote(result);
      setMessage("Quote refreshed");
      setError(null);
    } catch (caught) {
      showError(caught);
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    clearSession("Signed out");
    setError(null);
  }

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Atlas Wallet</p>
          <h1>Multi-currency money movement with traceable exchange rates.</h1>
          <p className="lede">Create wallets, move balances across currencies, inspect every rate and transfer with senior-engineering clarity.</p>
        </div>
        <div className="hero-card">
          <span>Portfolio signal</span>
          <strong>{profile ? money(defaultCurrencyTotal.toFixed(2), profile.default_currency) : "Secure by design"}</strong>
          <small>{wallets.length ? `Converted across ${wallets.length} active wallets` : "JWT, validation, health checks and transaction history"}</small>
        </div>
      </section>

      {message && <div className="toast success">{message}</div>}
      {error && <div className="toast danger">{error}</div>}

      {!signedIn ? (
        <section className="auth-panel panel">
          <div>
            <p className="eyebrow">Access</p>
            <h2>{authMode === "signup" ? "Open an account" : "Welcome back"}</h2>
            <p>Use the API-backed form to create a profile and your first default wallet.</p>
          </div>
          <form onSubmit={submitAuth} className="grid-form">
            <label>
              Email
              <input value={authForm.email} onChange={(event) => setAuthForm({ ...authForm, email: event.target.value })} type="email" required />
            </label>
            <label>
              Password
              <input value={authForm.password} onChange={(event) => setAuthForm({ ...authForm, password: event.target.value })} type="password" required />
            </label>
            {authMode === "signup" && (
              <>
                <label>
                  Display name
                  <input value={authForm.display_name} onChange={(event) => setAuthForm({ ...authForm, display_name: event.target.value })} required />
                </label>
                <label>
                  Default currency
                  <select value={authForm.default_currency} onChange={(event) => setAuthForm({ ...authForm, default_currency: event.target.value as Currency })}>
                    {currencies.map((currency) => (
                      <option key={currency}>{currency}</option>
                    ))}
                  </select>
                </label>
                <label className="wide">
                  Photo URL
                  <input value={authForm.photo_url} onChange={(event) => setAuthForm({ ...authForm, photo_url: event.target.value })} />
                </label>
              </>
            )}
            <button disabled={busy}>{busy ? "Working..." : authMode === "signup" ? "Create account" : "Sign in"}</button>
            <button type="button" className="ghost" onClick={() => setAuthMode(authMode === "signup" ? "login" : "signup")}>
              Switch to {authMode === "signup" ? "login" : "signup"}
            </button>
          </form>
        </section>
      ) : (
        <div className="dashboard">
          <section className="panel profile-card">
            <div className="profile-head">
              <div className="avatar">{profile?.photo_url ? <img src={profile.photo_url} alt="Profile" /> : profile?.display_name.slice(0, 1)}</div>
              <div>
                <p className="eyebrow">Profile</p>
                <h2>{profile?.display_name}</h2>
                <p>{profile?.email}</p>
              </div>
              <button type="button" className="ghost" onClick={logout}>Logout</button>
            </div>
            <form onSubmit={updateProfile} className="grid-form compact">
              <label>
                Display name
                <input value={profileForm.display_name} onChange={(event) => setProfileForm({ ...profileForm, display_name: event.target.value })} />
              </label>
              <label>
                Default currency
                <select value={profileForm.default_currency} onChange={(event) => setProfileForm({ ...profileForm, default_currency: event.target.value as Currency })}>
                  {currencies.map((currency) => (
                    <option key={currency}>{currency}</option>
                  ))}
                </select>
              </label>
              <label className="wide">
                Photo URL
                <input value={profileForm.photo_url} onChange={(event) => setProfileForm({ ...profileForm, photo_url: event.target.value })} />
              </label>
              <button disabled={busy}>Save profile</button>
            </form>
          </section>

          <section className="wallet-grid">
            {wallets.map((wallet) => (
              <article className="wallet-card" key={wallet.id}>
                <span>{wallet.currency}</span>
                <strong>{money(wallet.balance, wallet.currency)}</strong>
                <small>v{wallet.version} updated {compactDate(wallet.updated_at)}</small>
              </article>
            ))}
          </section>

          <section className="panel actions">
            <div>
              <p className="eyebrow">Wallet movement</p>
              <h2>Credit or debit with conversion</h2>
            </div>
            <form className="grid-form compact" onSubmit={(event) => event.preventDefault()}>
              <label>
                Amount
                <input value={moneyForm.amount} onChange={(event) => setMoneyForm({ ...moneyForm, amount: event.target.value })} inputMode="decimal" required />
              </label>
              <CurrencySelect label="Input currency" value={moneyForm.currency} onChange={(currency) => setMoneyForm({ ...moneyForm, currency })} />
              <CurrencySelect label="Wallet currency" value={moneyForm.wallet_currency} onChange={(currency) => setMoneyForm({ ...moneyForm, wallet_currency: currency })} />
              <label>
                Idempotency key
                <input value={moneyForm.idempotency_key} onChange={(event) => setMoneyForm({ ...moneyForm, idempotency_key: event.target.value })} placeholder="optional retry key" />
              </label>
              <label className="wide">
                Description
                <input value={moneyForm.description} onChange={(event) => setMoneyForm({ ...moneyForm, description: event.target.value })} />
              </label>
              <div className="button-row wide">
                <button type="button" disabled={busy} onClick={() => postMoney("/wallets/credit")}>Credit</button>
                <button type="button" disabled={busy} className="danger-button" onClick={() => postMoney("/wallets/debit")}>Debit</button>
              </div>
            </form>
          </section>

          <section className="panel actions">
            <div>
              <p className="eyebrow">Transfers</p>
              <h2>Move funds to another user atomically</h2>
            </div>
            <form className="grid-form compact" onSubmit={submitTransfer}>
              <label className="wide">
                Recipient email
                <input value={transferForm.recipient_email} onChange={(event) => setTransferForm({ ...transferForm, recipient_email: event.target.value })} type="email" required />
              </label>
              <label>
                Amount
                <input value={transferForm.amount} onChange={(event) => setTransferForm({ ...transferForm, amount: event.target.value })} inputMode="decimal" required />
              </label>
              <CurrencySelect label="Input currency" value={transferForm.currency} onChange={(currency) => setTransferForm({ ...transferForm, currency })} />
              <CurrencySelect label="Debit wallet" value={transferForm.source_wallet_currency} onChange={(currency) => setTransferForm({ ...transferForm, source_wallet_currency: currency })} />
              <CurrencySelect label="Recipient wallet" value={transferForm.target_wallet_currency} onChange={(currency) => setTransferForm({ ...transferForm, target_wallet_currency: currency })} />
              <label>
                Idempotency key
                <input value={transferForm.idempotency_key} onChange={(event) => setTransferForm({ ...transferForm, idempotency_key: event.target.value })} />
              </label>
              <label className="wide">
                Description
                <input value={transferForm.description} onChange={(event) => setTransferForm({ ...transferForm, description: event.target.value })} />
              </label>
              <button disabled={busy}>Post transfer</button>
            </form>
          </section>

          <section className="panel split-panel">
            <div>
              <p className="eyebrow">Exchange desk</p>
              <h2>Quote and provider trace</h2>
              <form onSubmit={fetchQuote} className="quote-form">
                <label>
                  Quote amount
                  <input value={quoteForm.amount} onChange={(event) => setQuoteForm({ ...quoteForm, amount: event.target.value })} />
                </label>
                <label>
                  From
                  <select value={quoteForm.source_currency} onChange={(event) => setQuoteForm({ ...quoteForm, source_currency: event.target.value as Currency })}>
                    {currencies.map((currency) => (
                      <option key={currency}>{currency}</option>
                    ))}
                  </select>
                </label>
                <label>
                  To
                  <select value={quoteForm.target_currency} onChange={(event) => setQuoteForm({ ...quoteForm, target_currency: event.target.value as Currency })}>
                    {currencies.map((currency) => (
                      <option key={currency}>{currency}</option>
                    ))}
                  </select>
                </label>
                <button disabled={busy}>Quote</button>
              </form>
              {quote && (
                <div className="quote-card">
                  <strong>{money(quote.target_amount, quote.target_currency)}</strong>
                  <span>{quote.source_amount} {quote.source_currency} at {quote.exchange_rate_value}</span>
                  <small>{quote.provider} · {compactDate(quote.fetched_at)}</small>
                </div>
              )}
            </div>
            <div className="rates-list">
              {rates.map((rate) => (
                <div key={rate.currency}>
                  <span>{rate.currency}</span>
                  <strong>{rate.rate}</strong>
                  <small>{rate.provider}</small>
                </div>
              ))}
            </div>
          </section>

          <section className="panel history">
            <div className="history-head">
              <div>
                <p className="eyebrow">Ledger</p>
                <h2>Transaction history</h2>
              </div>
              <div className="filters">
                <label>
                  Ledger kind
                  <select value={historyFilter.kind} onChange={(event) => setHistoryFilter({ ...historyFilter, kind: event.target.value as TransactionKind | "", page: 1 })}>
                    {kinds.map((kind) => (
                      <option key={kind || "all"} value={kind}>{kind || "all kinds"}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Ledger currency
                  <select value={historyFilter.currency} onChange={(event) => setHistoryFilter({ ...historyFilter, currency: event.target.value as Currency | "", page: 1 })}>
                    <option value="">all currencies</option>
                    {currencies.map((currency) => (
                      <option key={currency}>{currency}</option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
            <div className="transaction-list">
              {transactions.items.map((transaction) => (
                <article key={transaction.id} className="transaction-row">
                  <div>
                    <strong>{transaction.kind.replace("_", " ")}</strong>
                    <span>{transaction.description || "No description"}</span>
                    <small>Rate {transaction.exchange_rate_value} from {transaction.exchange_provider} at {compactDate(transaction.exchange_fetched_at)}</small>
                  </div>
                  <div>
                    <strong>{money(transaction.wallet_amount, transaction.wallet_currency)}</strong>
                    <span>{compactDate(transaction.created_at)}</span>
                    <small>related #{transaction.related_transaction_id || "none"}</small>
                  </div>
                </article>
              ))}
              {!transactions.items.length && <p className="empty">No transactions match the current filters.</p>}
            </div>
            <div className="pager">
              <button disabled={historyFilter.page <= 1} onClick={() => setHistoryFilter({ ...historyFilter, page: historyFilter.page - 1 })}>Previous</button>
              <span>Page {transactions.page} · {transactions.total} total</span>
              <button disabled={historyFilter.page * transactions.page_size >= transactions.total} onClick={() => setHistoryFilter({ ...historyFilter, page: historyFilter.page + 1 })}>Next</button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function CurrencySelect({ label, value, onChange }: { label: string; value: Currency; onChange: (currency: Currency) => void }) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value as Currency)}>
        {currencies.map((currency) => (
          <option key={currency}>{currency}</option>
        ))}
      </select>
    </label>
  );
}

export default App;
