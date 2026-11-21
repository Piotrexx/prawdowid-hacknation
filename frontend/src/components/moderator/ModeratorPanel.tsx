"use client";

import { LogOut } from "lucide-react";
import { useId, useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/Button";
import { useAdminToken, writeAdminToken } from "@/lib/adminToken";
import { cx } from "@/lib/cx";
import { CasesTab } from "./CasesTab";
import { ChecksTab } from "./ChecksTab";
import { EventsTab } from "./EventsTab";
import { ExportButtons } from "./ExportButtons";
import { MetricsTab } from "./MetricsTab";
import { TokenPrompt } from "./TokenPrompt";
import type { AdminAccess } from "./useAdminData";

const TABS = [
  { key: "cases", label: "Sprawy", Panel: CasesTab },
  { key: "metrics", label: "Statystyki", Panel: MetricsTab },
  { key: "events", label: "Zdarzenia bezpieczeństwa", Panel: EventsTab },
  { key: "checks", label: "Zgłoszenia", Panel: ChecksTab },
] as const;

type TabKey = (typeof TABS)[number]["key"];

function Dashboard({ access, onLogout }: { access: AdminAccess; onLogout: () => void }) {
  const baseId = useId();
  const [active, setActive] = useState<TabKey>("cases");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const ActivePanel = TABS.find((tab) => tab.key === active)?.Panel ?? CasesTab;

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const current = TABS.findIndex((tab) => tab.key === active);
    const last = TABS.length - 1;
    const next =
      event.key === "ArrowRight"
        ? (current + 1) % TABS.length
        : event.key === "ArrowLeft"
          ? (current + last) % TABS.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : null;
    if (next === null) return;
    event.preventDefault();
    setActive(TABS[next].key);
    tabRefs.current[next]?.focus();
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <ExportButtons access={access} />
        <Button onClick={onLogout}>
          <LogOut aria-hidden="true" className="size-5" />
          Wyloguj
        </Button>
      </div>

      <div
        role="tablist"
        aria-label="Sekcje panelu moderatora"
        onKeyDown={handleKeyDown}
        className="flex flex-wrap gap-1 border-b border-line-strong"
      >
        {TABS.map((tab, index) => {
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

export function ModeratorPanel() {
  const token = useAdminToken();
  const [notice, setNotice] = useState<string | null>(null);
  const [closed, setClosed] = useState(false);

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

  const access: AdminAccess = {
    token,
    onUnauthorized: () => {
      writeAdminToken(null);
      setClosed(true);
      setNotice("Serwer odrzucił token. Podaj go ponownie.");
    },
  };

  return (
    <Dashboard
      access={access}
      onLogout={() => {
        setNotice(null);
        setClosed(true);
        writeAdminToken(null);
      }}
    />
  );
}
