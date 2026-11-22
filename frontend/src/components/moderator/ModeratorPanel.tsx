"use client";

import { LogOut } from "lucide-react";
import { useId, useRef, useState, useEffect, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/Button";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { getProfile, logoutModerator } from "@/lib/api";
import { useAdminToken, writeAdminToken } from "@/lib/adminToken";
import { cx } from "@/lib/cx";
import type { Profile } from "@/lib/types";
import { AccountTab } from "./AccountTab";
import { CasesTab } from "./CasesTab";
import { ChecksTab } from "./ChecksTab";
import { EventsTab } from "./EventsTab";
import { ExportButtons } from "./ExportButtons";
import { LlmTab } from "./LlmTab";
import { ModeratorsTab } from "./ModeratorsTab";
import { MetricsTab } from "./MetricsTab";
import { TokenPrompt } from "./TokenPrompt";
import { useAdminData, type AdminAccess } from "./useAdminData";

interface TabDefinition {
  key: string;
  label: string;
  Panel: (props: { access: AdminAccess }) => ReactNode;
}

function AccountBadge({ profile, onLogout }: { profile: Profile; onLogout: () => void }) {
  const { display_name, email } = profile.moderator;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-2 border-line-strong bg-surface px-3 py-2">
      <p className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="font-semibold">{display_name || email}</span>
        {display_name ? <span className="text-sm text-muted">{email}</span> : null}
      </p>
      <Button variant="danger" onClick={onLogout}>
        <LogOut aria-hidden="true" className="size-5" />
        Wyloguj
      </Button>
    </div>
  );
}

function Dashboard({
  access,
  profile,
  onLogout,
}: {
  access: AdminAccess;
  profile: Profile;
  onLogout: () => void;
}) {
  const baseId = useId();
  const [headerSlot, setHeaderSlot] = useState<HTMLElement | null>(null);
  const [lowerSlot, setLowerSlot] = useState<HTMLDivElement | null>(null);
  const [stixHelpOpen, setStixHelpOpen] = useState(false);
  const accountSlot = stixHelpOpen ? lowerSlot : headerSlot;
  const isSuperuser = profile.moderator.role === "superuser";
  const tabs: TabDefinition[] = [
    { key: "cases", label: "Twierdzenia", Panel: CasesTab },
    { key: "account", label: "Konto", Panel: AccountTab },
    { key: "metrics", label: "Statystyki", Panel: MetricsTab },
    { key: "events", label: "Zdarzenia bezpieczeństwa", Panel: EventsTab },
    { key: "checks", label: "Zgłoszenia", Panel: ChecksTab },
    ...(isSuperuser
      ? [
          { key: "llm", label: "Model AI", Panel: LlmTab },
          { key: "moderators", label: "Moderatorzy", Panel: ModeratorsTab },
        ]
      : []),
  ];
  const [active, setActive] = useState<string>("cases");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const ActivePanel = tabs.find((tab) => tab.key === active)?.Panel ?? CasesTab;

  useEffect(() => {
    // Konto jest renderowane w nagłówku strony, obok tytułu „Panel moderatora”.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- docelowy element istnieje tylko w DOM
    setHeaderSlot(document.getElementById("moderator-account-slot"));
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const current = tabs.findIndex((tab) => tab.key === active);
    const last = tabs.length - 1;
    const next =
      event.key === "ArrowRight"
        ? (current + 1) % tabs.length
        : event.key === "ArrowLeft"
          ? (current + last) % tabs.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : null;
    if (next === null) return;
    event.preventDefault();
    setActive(tabs[next].key);
    tabRefs.current[next]?.focus();
  }

  return (
    <div className="space-y-6">
      {accountSlot
        ? createPortal(<AccountBadge profile={profile} onLogout={onLogout} />, accountSlot)
        : null}

      <ExportButtons access={access} onStixHelpToggle={setStixHelpOpen} />
      {/* Konto przenosi się tutaj, gdy rozwinięta jest pomoc eksportu STIX. */}
      <div ref={setLowerSlot} className="flex justify-end empty:hidden" />

      {profile.moderator.must_change_password ? (
        <p
          role="status"
          className="rounded-lg border border-warn-line bg-warn-bg px-4 py-3 font-medium text-warn-fg"
        >
          To konto ma hasło startowe. Zmień je w zakładce „Konto”.
        </p>
      ) : null}

      <div
        role="tablist"
        aria-label="Sekcje panelu moderatora"
        onKeyDown={handleKeyDown}
        className="flex flex-wrap gap-1 border-b border-line-strong"
      >
        {tabs.map((tab, index) => {
          const selected = tab.key === active;
          return (
            <button
              key={tab.key}
              ref={(element) => {
                tabRefs.current[index] = element;
              }}
              type="button"
              role="tab"
              id={`${baseId}-tab-${tab.key}`}
              aria-selected={selected}
              aria-controls={`${baseId}-panel`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActive(tab.key)}
              className={cx(
                "min-h-11 rounded-t-lg border-b-4 px-4 font-medium",
                selected
                  ? "border-accent bg-surface text-ink"
                  : "border-transparent text-muted hover:bg-subtle hover:text-ink",
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div
        role="tabpanel"
        id={`${baseId}-panel`}
        aria-labelledby={`${baseId}-tab-${active}`}
        tabIndex={0}
      >
        <ActivePanel key={active} access={access} />
      </div>
    </div>
  );
}

function AuthenticatedPanel({
  token,
  onLogout,
}: {
  token: string;
  onLogout: (notice: string | null) => void;
}) {
  const { state, reload } = useAdminData({ token, onUnauthorized: () => onLogout(null) }, "me", getProfile);
  if (state.status === "loading") return <LoadingBlock label="Wczytuję konto…" />;
  if (state.status === "error") {
    return <ErrorBlock error={state.error} onRetry={reload} />;
  }
  return (
    <Dashboard
      access={{
        token,
        onUnauthorized: () => onLogout(null),
        moderatorId: state.data.moderator.id || undefined,
        isSuperuser: state.data.moderator.role === "superuser",
      }}
      profile={state.data}
      onLogout={() => onLogout(null)}
    />
  );
}

export function ModeratorPanel() {
  const token = useAdminToken();
  const [notice, setNotice] = useState<string | null>(null);
  const [closed, setClosed] = useState(false);
  const [autoLogin, setAutoLogin] = useState(false);

  useEffect(() => {
    const current = new URL(window.location.href);
    const hash = new URLSearchParams(current.hash.replace(/^#/, ""));
    const candidate = hash.get("token") ?? current.searchParams.get("token");
    if (!candidate) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAutoLogin(true);
    getProfile(candidate)
      .then(() => {
        if (cancelled) return;
        writeAdminToken(candidate);
        setNotice(null);
      })
      .catch(() => {
        if (!cancelled) {
          setNotice(
            "Link logowania jest nieprawidłowy albo wygasł. Zaloguj się ręcznie.",
          );
        }
      })
      .finally(() => {
        if (cancelled) return;
        setAutoLogin(false);
        // Token nie zostaje w pasku adresu ani w historii przeglądarki.
        const clean = new URL(window.location.href);
        clean.hash = "";
        clean.searchParams.delete("token");
        window.history.replaceState(null, "", clean.pathname + clean.search);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (autoLogin) {
    return <LoadingBlock label="Łączę z kontem…" />;
  }

  if (!token) {
    return (
      <TokenPrompt
        notice={notice}
        takeFocus={closed}
        onAccepted={(accepted) => {
          setNotice(null);
          writeAdminToken(accepted);
        }}
      />
    );
  }

  return (
    <AuthenticatedPanel
      token={token}
      onLogout={(message) => {
        void logoutModerator(token).catch(() => undefined);
        setNotice(message);
        setClosed(true);
        writeAdminToken(null);
      }}
    />
  );
}
