"use client";

import {
  BookOpen,
  Menu,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  SquarePen,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { HistoryList } from "@/components/chat/HistoryList";
import { cx } from "@/lib/cx";
import { requestNewCheck } from "@/lib/newCheck";
import { setSidebarCollapsed, useSidebarCollapsed } from "@/lib/sidebar";
import { AccessibilitySettings } from "./AccessibilitySettings";

const NAV_ITEMS: Array<{ href: string; label: string; icon: LucideIcon }> = [
  { href: "/", label: "Sprawdź", icon: MessageSquareText },
  { href: "/zrodla", label: "Źródła", icon: BookOpen },
];

function isCurrent(pathname: string | null, href: string): boolean {
  if (pathname === null) return false;
  if (href === "/") return pathname === "/" || pathname.startsWith("/sprawdzenie");
  return pathname.startsWith(href);
}

function NavList({ pathname, onNavigate }: { pathname: string | null; onNavigate?: () => void }) {
  return (
    <ul className="flex flex-col gap-0.5">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const current = isCurrent(pathname, href);
        return (
          <li key={href}>
            <Link
              href={href}
              aria-current={current ? "page" : undefined}
              onClick={onNavigate}
              title={label}
              className={cx(
                "flex min-h-11 items-center gap-3 border-l-[3px] px-3 transition-colors collapsed:justify-center collapsed:px-0",
                current
                  ? "border-accent bg-surface font-bold text-accent"
                  : "border-transparent text-ink hover:bg-surface hover:text-accent",
              )}
            >
              <Icon aria-hidden="true" className="size-5 shrink-0" />
              <span className="collapsed:sr-only">{label}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function CurrentNavList({ onNavigate }: { onNavigate?: () => void }) {
  return <NavList pathname={usePathname()} onNavigate={onNavigate} />;
}

function Brand({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Link
      href="/"
      onClick={onNavigate}
      className="inline-flex min-h-11 items-center text-[1.625rem] leading-none font-bold tracking-[-0.02em] text-ink"
    >
      Prawdowid
      <span className="sr-only"> – strona główna</span>
    </Link>
  );
}

/** Starts a fresh conversation, from any page. */
function useStartNewCheck(onNavigate?: () => void) {
  const router = useRouter();
  return () => {
    requestNewCheck();
    if (window.location.pathname !== "/") router.push("/");
    onNavigate?.();
  };
}

function CollapseToggle() {
  const collapsed = useSidebarCollapsed();
  return (
    <button
      type="button"
      aria-expanded={!collapsed}
      aria-controls="menu-boczne-desktop"
      onClick={() => setSidebarCollapsed(!collapsed)}
      title={collapsed ? "Rozwiń menu" : "Zwiń menu"}
      className="grid size-11 shrink-0 place-items-center text-muted transition-colors hover:bg-surface hover:text-accent"
    >
      {/* Icons follow the CSS state, so a saved collapsed rail is right before hydration. */}
      <PanelLeftClose aria-hidden="true" className="size-5.5 collapsed:hidden" />
      <PanelLeftOpen aria-hidden="true" className="hidden size-5.5 collapsed:block" />
      <span className="sr-only">{collapsed ? "Rozwiń menu" : "Zwiń menu"}</span>
    </button>
  );
}

interface SidebarContentProps {
  /** Keeps ids unique between the desktop sidebar and the phone drawer. */
  idPrefix: string;
  onNavigate?: () => void;
}

function SidebarContent({ idPrefix, onNavigate }: SidebarContentProps) {
  const startNewCheck = useStartNewCheck(onNavigate);
  const historyId = `${idPrefix}-historia`;

  return (
    <>
      <div className="flex flex-col gap-4 px-4 pt-5 collapsed:px-0 collapsed:pt-3">
        <div className="hidden items-center justify-between gap-2 pl-1 lg:flex collapsed:justify-center collapsed:pl-0">
          <span className="collapsed:hidden">
            <Brand onNavigate={onNavigate} />
          </span>
          {idPrefix === "boczny" ? <CollapseToggle /> : null}
        </div>
        <nav aria-label="Główna nawigacja" className="-mx-4 collapsed:mx-0">
          {/* On routes with a dynamic segment the pathname is unknown while prerendering. */}
          <Suspense fallback={<NavList pathname={null} onNavigate={onNavigate} />}>
            <CurrentNavList onNavigate={onNavigate} />
          </Suspense>
        </nav>
      </div>

      <section
        aria-labelledby={historyId}
        className="mt-4 flex min-h-0 flex-1 flex-col border-t border-line pt-4"
      >
        <h2 id={historyId} className="eyebrow mb-2 px-5 collapsed:sr-only">
          Twoje sesje
        </h2>
        {/* The list shrinks and scrolls, so the button under it stays in view. */}
        <div className="min-h-0 shrink overflow-y-auto px-2 collapsed:hidden">
          <HistoryList onNavigate={onNavigate} />
        </div>
        <div className="shrink-0 pt-1 pb-2">
          <button
            type="button"
            onClick={startNewCheck}
            title="Nowa sesja"
            className="flex min-h-11 w-full items-center gap-3 px-[0.9375rem] text-left text-ink transition-colors hover:bg-surface hover:text-accent collapsed:justify-center collapsed:px-0"
          >
            <Plus aria-hidden="true" className="size-5 shrink-0" />
            <span className="collapsed:sr-only">Nowa sesja</span>
          </button>
        </div>
      </section>

      <div className="border-t border-line px-4 pt-3 pb-4 collapsed:px-2">
        <AccessibilitySettings placement="above" />
      </div>
    </>
  );
}

function MobileBar() {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  const startNewCheck = useStartNewCheck();

  useEffect(() => {
    if (open) {
      wasOpen.current = true;
      closeRef.current?.focus();
      const previous = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      const onKey = (event: KeyboardEvent) => {
        if (event.key === "Escape") setOpen(false);
      };
      document.addEventListener("keydown", onKey);
      return () => {
        document.body.style.overflow = previous;
        document.removeEventListener("keydown", onKey);
      };
    }
    if (wasOpen.current) menuRef.current?.focus();
  }, [open]);

  const close = () => setOpen(false);

  return (
    <>
      <div className="sticky top-0 z-30 flex items-center gap-1 border-b border-line bg-surface px-2 py-1.5 lg:hidden">
        <button
          ref={menuRef}
          type="button"
          aria-expanded={open}
          aria-controls="menu-boczne"
          onClick={() => setOpen(true)}
          className="grid size-11 place-items-center text-ink hover:bg-subtle"
        >
          <Menu aria-hidden="true" className="size-6" />
          <span className="sr-only">Otwórz menu</span>
        </button>
        <Brand />
        <span className="flex-1" />
        <button
          type="button"
          onClick={startNewCheck}
          className="grid size-11 place-items-center text-accent hover:bg-subtle"
        >
          <SquarePen aria-hidden="true" className="size-5.5" />
          <span className="sr-only">Nowa sesja</span>
        </button>
      </div>

      {open ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            tabIndex={-1}
            aria-hidden="true"
            onClick={close}
            className="absolute inset-0 bg-ink/40"
          />
          <div
            id="menu-boczne"
            role="dialog"
            aria-modal="true"
            aria-label="Menu"
            className="absolute inset-y-0 left-0 flex w-[min(20rem,88vw)] flex-col bg-subtle shadow-card"
          >
            <div className="flex items-center justify-between border-b border-line py-1.5 pr-2 pl-5">
              <Brand onNavigate={close} />
              <button
                ref={closeRef}
                type="button"
                onClick={close}
                className="grid size-11 place-items-center text-ink hover:bg-surface"
              >
                <X aria-hidden="true" className="size-6" />
                <span className="sr-only">Zamknij menu</span>
              </button>
            </div>
            <SidebarContent idPrefix="szuflada" onNavigate={close} />
          </div>
        </div>
      ) : null}
    </>
  );
}

export function AppSidebar() {
  return (
    <>
      <MobileBar />
      <aside
        id="menu-boczne-desktop"
        aria-label="Menu boczne"
        data-rail
        className="sticky top-0 hidden h-dvh w-72 shrink-0 flex-col border-r border-line bg-subtle transition-[width] duration-200 lg:flex rail-collapsed:w-16"
      >
        <SidebarContent idPrefix="boczny" />
      </aside>
    </>
  );
}
