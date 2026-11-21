"use client";

import { useEffect, useRef, useState } from "react";
import { Download, KeyRound, LogOut, RefreshCw, ShieldCheck } from "lucide-react";
import { API_BASE } from "@/lib/api";
import type { AdminCheckItem, AdminMetrics } from "@/lib/types";

const SESSION_KEY = "moderator_token";

const VERDICT_PL: Record<string, string> = {
  potwierdzone: "Potwierdzone",
  falszywe: "Fałszywe",
  wprowadzajace_w_blad: "Wprowadzające w błąd",
  brak_wystarczajacych_dowodow: "Brak dowodów",
  nie_podlega_weryfikacji: "Nie podlega weryfikacji",
};

const STATUS_PL: Record<string, string> = {
  completed: "Zakończone",
  error: "Błąd",
  needs_clarification: "Wymaga doprecyzowania",
  out_of_scope: "Poza zakresem",
};

function fmt(ms: number | null | undefined) {
  if (ms == null) return "—";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("pl-PL", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

async function adminFetch<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}/admin${path}`, {
    headers: { "X-Admin-Token": token },
  });
  if (res.status === 401 || res.status === 403) throw new Error("unauthorized");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

// --- Login screen ---

function LoginForm({ onLogin }: { onLogin: (token: string) => void }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;
    setError(false);
    // We validate the token by trying to call the API; for now pass immediately
    // and let the dashboard show the 401 if wrong.
    onLogin(value.trim());
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-page px-4">
      <div className="w-full max-w-sm space-y-6 border border-line bg-surface p-8">
        <div className="flex items-center gap-3">
          <ShieldCheck className="size-7 text-accent" />
          <div>
            <p className="eyebrow">Panel moderatora</p>
            <p className="text-sm text-muted">Wymagane hasło administratora</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="admin-token" className="mb-1.5 block text-sm font-medium">
              Token administratora
            </label>
            <input
              ref={inputRef}
              id="admin-token"
              type="password"
              autoComplete="current-password"
              value={value}
              onChange={(e) => { setValue(e.target.value); setError(false); }}
              className="w-full border border-line bg-subtle px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent"
              placeholder="••••••••"
            />
          </div>
          {error && (
            <p className="text-sm text-bad-fg" role="alert">
              Nieprawidłowy token – sprawdź zmienną ADMIN_TOKEN.
            </p>
          )}
          <button
            type="submit"
            className="flex w-full items-center justify-center gap-2 bg-accent px-4 py-2 text-sm font-semibold text-on-accent hover:bg-accent-hover"
          >
            <KeyRound className="size-4" />
            Wejdź do panelu
          </button>
        </form>
      </div>
    </div>
  );
}

// --- Metric tile ---

function Tile({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="border border-line bg-surface p-4">
      <p className="eyebrow mb-1">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
      {sub && <p className="mt-0.5 text-sm text-muted">{sub}</p>}
    </div>
  );
}

// --- Main dashboard ---

function Dashboard({ token, onLogout }: { token: string; onLogout: () => void }) {
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [checks, setChecks] = useState<AdminCheckItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [m, c] = await Promise.all([
        adminFetch<AdminMetrics>("/metrics", token),
        adminFetch<AdminCheckItem[]>("/checks?limit=100", token),
      ]);
      setMetrics(m);
      setChecks(c);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg === "unauthorized") {
        setError("Nieprawidłowy token administratora.");
      } else {
        setError(`Błąd ładowania danych: ${msg}`);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [token]);

  function downloadExport(format: "csv" | "json") {
    const url = `${API_BASE}/admin/export?format=${format}`;
    const a = document.createElement("a");
    a.href = url;
    a.download = `prawdowid-export.${format}`;
    // Pass token via a temporary fetch and blob download so the header is sent
    fetch(url, { headers: { "X-Admin-Token": token } })
      .then((r) => r.blob())
      .then((blob) => {
        a.href = URL.createObjectURL(blob);
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(() => setError("Nie udało się pobrać eksportu."));
  }

  return (
    <div className="min-h-screen bg-page">
      {/* Header */}
      <header className="border-b border-line bg-surface px-6 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-accent" />
            <span className="font-semibold">Panel moderatora</span>
            <span className="ml-2 rounded bg-warn-bg px-2 py-0.5 text-xs font-medium text-warn-fg">
              Tylko do użytku wewnętrznego
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => void load()}
              className="flex items-center gap-1.5 border border-line px-3 py-1.5 text-sm hover:bg-subtle"
              disabled={loading}
            >
              <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
              Odśwież
            </button>
            <button
              onClick={onLogout}
              className="flex items-center gap-1.5 border border-line px-3 py-1.5 text-sm hover:bg-subtle"
            >
              <LogOut className="size-4" />
              Wyloguj
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-8 px-6 py-8">
        {error && (
          <div role="alert" className="border-2 border-bad-line bg-bad-bg p-4 text-bad-fg">
            {error}
          </div>
        )}

        {metrics && (
          <>
            {/* Top-level metrics */}
            <section aria-label="Statystyki ogólne">
              <h2 className="mb-4 text-lg font-semibold">Statystyki</h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                <Tile label="Łącznie" value={metrics.checks_total} />
                <Tile
                  label="Zakończone"
                  value={metrics.by_status["completed"] ?? 0}
                />
                <Tile
                  label="Błędy"
                  value={metrics.by_status["error"] ?? 0}
                />
                <Tile
                  label="Śr. fact-checki"
                  value={metrics.avg_factchecks}
                />
                <Tile
                  label="Mediana czasu"
                  value={fmt(metrics.median_duration_ms)}
                />
                <Tile
                  label="Kanały"
                  value={Object.keys(metrics.by_channel).length}
                  sub={Object.keys(metrics.by_channel).join(", ")}
                />
              </div>
            </section>

            {/* Verdicts + errors side by side */}
            <div className="grid gap-6 md:grid-cols-2">
              <section aria-label="Rozkład werdyktów">
                <h2 className="mb-3 text-lg font-semibold">Werdykty</h2>
                <div className="border border-line bg-surface">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-line bg-subtle">
                        <th className="px-4 py-2 text-left font-medium">Werdykt</th>
                        <th className="px-4 py-2 text-right font-medium">Liczba</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(metrics.by_verdict).length === 0 ? (
                        <tr>
                          <td colSpan={2} className="px-4 py-3 text-muted">
                            Brak zakończonych sprawdzeń.
                          </td>
                        </tr>
                      ) : (
                        Object.entries(metrics.by_verdict).map(([v, n]) => (
                          <tr key={v} className="border-b border-line last:border-0">
                            <td className="px-4 py-2">{VERDICT_PL[v] ?? v}</td>
                            <td className="px-4 py-2 text-right font-mono">{n}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              <section aria-label="Kody błędów">
                <h2 className="mb-3 text-lg font-semibold">Błędy techniczne</h2>
                <div className="border border-line bg-surface">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-line bg-subtle">
                        <th className="px-4 py-2 text-left font-medium">Kod błędu</th>
                        <th className="px-4 py-2 text-right font-medium">Liczba</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(metrics.errors).length === 0 ? (
                        <tr>
                          <td colSpan={2} className="px-4 py-3 text-muted">
                            Brak błędów.
                          </td>
                        </tr>
                      ) : (
                        Object.entries(metrics.errors).map(([code, n]) => (
                          <tr key={code} className="border-b border-line last:border-0">
                            <td className="px-4 py-2 font-mono text-bad-fg">{code}</td>
                            <td className="px-4 py-2 text-right font-mono">{n}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </>
        )}

        {/* Checks table */}
        <section aria-label="Ostatnie sprawdzenia">
          <div className="mb-3 flex items-center justify-between gap-4">
            <h2 className="text-lg font-semibold">
              Ostatnie sprawdzenia
              {checks.length > 0 && (
                <span className="ml-2 text-sm font-normal text-muted">
                  ({checks.length})
                </span>
              )}
            </h2>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted">Eksport:</span>
              <button
                onClick={() => downloadExport("csv")}
                className="flex items-center gap-1.5 border border-line px-3 py-1.5 text-sm hover:bg-subtle"
              >
                <Download className="size-3.5" />
                CSV
              </button>
              <button
                onClick={() => downloadExport("json")}
                className="flex items-center gap-1.5 border border-line px-3 py-1.5 text-sm hover:bg-subtle"
              >
                <Download className="size-3.5" />
                JSON
              </button>
            </div>
          </div>

          <div className="overflow-x-auto border border-line bg-surface">
            <table className="w-full min-w-[800px] text-sm">
              <thead>
                <tr className="border-b border-line bg-subtle text-left">
                  <th className="px-4 py-2 font-medium">Data</th>
                  <th className="px-4 py-2 font-medium">Kanał</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Werdykt</th>
                  <th className="px-4 py-2 font-medium">Ufność</th>
                  <th className="px-4 py-2 font-medium">Fact-cheki</th>
                  <th className="px-4 py-2 font-medium">Czas</th>
                  <th className="px-4 py-2 font-medium">Tytuł / Treść</th>
                </tr>
              </thead>
              <tbody>
                {loading && checks.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-6 text-center text-muted">
                      Ładowanie…
                    </td>
                  </tr>
                ) : checks.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-6 text-center text-muted">
                      Brak sprawdzeń.
                    </td>
                  </tr>
                ) : (
                  checks.map((c) => (
                    <tr key={c.id} className="border-b border-line last:border-0 hover:bg-subtle">
                      <td className="whitespace-nowrap px-4 py-2 text-muted">
                        {fmtDate(c.created_at)}
                      </td>
                      <td className="px-4 py-2">
                        <span className="rounded bg-info-bg px-1.5 py-0.5 text-xs font-medium text-info-fg">
                          {c.channel}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={
                            c.status === "error"
                              ? "rounded bg-bad-bg px-1.5 py-0.5 text-xs font-medium text-bad-fg"
                              : c.status === "completed"
                              ? "rounded bg-ok-bg px-1.5 py-0.5 text-xs font-medium text-ok-fg"
                              : "rounded bg-calm-bg px-1.5 py-0.5 text-xs font-medium text-calm-fg"
                          }
                        >
                          {STATUS_PL[c.status] ?? c.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-sm">
                        {c.verdict ? (VERDICT_PL[c.verdict] ?? c.verdict) : "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-sm">
                        {c.confidence != null ? `${Math.round(c.confidence * 100)}%` : "—"}
                      </td>
                      <td className="px-4 py-2 text-center font-mono text-sm">
                        {c.factcheck_count}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-sm text-muted">
                        {fmt(c.duration_ms)}
                      </td>
                      <td className="max-w-xs truncate px-4 py-2 text-muted">
                        {c.title ?? c.url ?? (
                          <span className="italic">brak tytułu</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}

// --- Page root with session-based auth ---

export default function ModeratorPage() {
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(SESSION_KEY);
      if (saved) setToken(saved);
    } catch {
      // sessionStorage blocked (private mode etc.) — just show login
    }
    setReady(true);
  }, []);

  function handleLogin(t: string) {
    try {
      sessionStorage.setItem(SESSION_KEY, t);
    } catch { /* ignore */ }
    setToken(t);
  }

  function handleLogout() {
    try {
      sessionStorage.removeItem(SESSION_KEY);
    } catch { /* ignore */ }
    setToken(null);
  }

  if (!ready) return null;

  if (!token) return <LoginForm onLogin={handleLogin} />;

  return <Dashboard token={token} onLogout={handleLogout} />;
}
