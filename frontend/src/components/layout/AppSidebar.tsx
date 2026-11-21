"use client";

import { BookOpen, ChevronLeft, ChevronRight, Menu, MessageSquareText, Plus, Shield, SquarePen, Trash2, X, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { HistoryList } from "@/components/chat/HistoryList";
import { cx } from "@/lib/cx";
import { clearHistory, useHistory } from "@/lib/history";
import { requestNewCheck } from "@/lib/newCheck";
import { AccessibilitySettings } from "./AccessibilitySettings";

function getNavItems(t: (key: string) => string) {
  return [
    { href: "/", label: t("nav.check"), icon: MessageSquareText },
    { href: "/zrodla", label: t("nav.sources"), icon: BookOpen },
    { href: "/prywatnosc", label: t("nav.privacy"), icon: Shield },
  ] as Array<{ href: string; label: string; icon: LucideIcon }>;
}

function isCurrent(pathname: string | null, href: string): boolean {
  if (pathname === null) return false;
  if (href === "/") return pathname === "/" || pathname.startsWith("/sprawdzenie");
  return pathname.startsWith(href);
}

function NavList({
  pathname,
  onNavigate,
  collapsed,
}: {
  pathname: string | null;
  onNavigate?: () => void;
  collapsed?: boolean;
}) {
  const { t } = useTranslation();
  const items = getNavItems(t);
  return (
    <ul className="flex flex-col gap-0.5">
      {items.map(({ href, label, icon: Icon }) => {
        const current = isCurrent(pathname, href);
        return (
          <li key={href}>
            <Link
              href={href}
              aria-current={current ? "page" : undefined}
              onClick={onNavigate}
              title={collapsed ? label : undefined}
              className={cx(
                "flex min-h-11 items-center gap-3 border-l-[3px] transition-colors",
                collapsed ? "justify-center px-2" : "px-3",
                current
                  ? "border-accent bg-surface font-bold text-accent"
                  : "border-transparent text-ink hover:bg-surface hover:text-accent",
              )}
            >
              <Icon aria-hidden="true" className="size-5 shrink-0" />
              {!collapsed && label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function CurrentNavList({
  onNavigate,
  collapsed,
}: {
  onNavigate?: () => void;
  collapsed?: boolean;
}) {
  return (
    <NavList pathname={usePathname()} onNavigate={onNavigate} collapsed={collapsed} />
  );
}

function Brand({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation();
  return (
    <Link
      href="/"
      onClick={onNavigate}
      className="inline-flex min-h-11 items-center text-[1.625rem] leading-none font-bold tracking-[-0.02em] text-ink"
    >
      Prawdowid
      <span className="sr-only">{t("nav.homeLink")}</span>
    </Link>
  );
}

function useStartNewCheck(onNavigate?: () => void) {
  const router = useRouter();
  return () => {
    requestNewCheck();
    if (window.location.pathname !== "/") router.push("/");
    onNavigate?.();
  };
}

interface SidebarContentProps {
  idPrefix: string;
  onNavigate?: () => void;
  collapsed?: boolean;
}

function SidebarContent({ idPrefix, onNavigate, collapsed }: SidebarContentProps) {
  const { t } = useTranslation();
  const startNewCheck = useStartNewCheck(onNavigate);
  const historyId = `${idPrefix}-historia`;
  const history = useHistory();

  return (
    <>
      <div className="flex flex-col gap-4 px-4 pt-5">
        {!collapsed && (
          <div className="hidden px-1 lg:block">
            <Brand onNavigate={onNavigate} />
          </div>
        )}
        <nav aria-label={t("nav.mainNav")} className="-mx-4">
          <Suspense fallback={<NavList pathname={null} onNavigate={onNavigate} collapsed={collapsed} />}>
            <CurrentNavList onNavigate={onNavigate} collapsed={collapsed} />
          </Suspense>
        </nav>
      </div>

      {!collapsed && (
        <section
          aria-labelledby={historyId}
          className="mt-4 flex min-h-0 flex-1 flex-col border-t border-line pt-4"
        >
          <div className="mb-2 flex items-center justify-between px-5">
            <h2 id={historyId} className="eyebrow">
              {t("sidebar.sessions")}
            </h2>
            {history?.length ? (
              <button
                type="button"
                onClick={clearHistory}
                title={t("sidebar.clearHistory")}
                className="grid size-7 place-items-center text-muted hover:text-accent"
              >
                <Trash2 aria-hidden="true" className="size-4" />
                <span className="sr-only">{t("sidebar.clearHistory")}</span>
              </button>
            ) : null}
          </div>
          <div className="min-h-0 shrink overflow-y-auto px-2">
            <HistoryList onNavigate={onNavigate} />
          </div>
          <div className="shrink-0 pt-1 pb-2">
            <button
              type="button"
              onClick={startNewCheck}
              className="flex min-h-11 w-full items-center gap-3 px-[0.9375rem] text-left text-ink transition-colors hover:bg-surface hover:text-accent"
            >
              <Plus aria-hidden="true" className="size-5 shrink-0" />
              {t("sidebar.newSession")}
            </button>
          </div>
        </section>
      )}

      {collapsed && (
        <div className="mt-4 flex flex-1 flex-col items-center border-t border-line pt-4">
          <button
            type="button"
            onClick={startNewCheck}
            title={t("sidebar.newSession")}
            className="grid size-11 place-items-center text-ink transition-colors hover:bg-surface hover:text-accent"
          >
            <Plus aria-hidden="true" className="size-5 shrink-0" />
            <span className="sr-only">{t("sidebar.newSession")}</span>
          </button>
        </div>
      )}

      {!collapsed && (
        <div className="border-t border-line px-4 pt-3 pb-4">
          <AccessibilitySettings placement="above" />
        </div>
      )}
    </>
  );
}

function MobileBar() {
  const { t } = useTranslation();
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
          <span className="sr-only">{t("sidebar.openMenu")}</span>
        </button>
        <Brand />
        <span className="flex-1" />
        <button
          type="button"
          onClick={startNewCheck}
          className="grid size-11 place-items-center text-accent hover:bg-subtle"
        >
          <SquarePen aria-hidden="true" className="size-5.5" />
          <span className="sr-only">{t("sidebar.newSession")}</span>
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
            aria-label={t("sidebar.menu")}
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
                <span className="sr-only">{t("sidebar.closeMenu")}</span>
              </button>
            </div>
            <SidebarContent idPrefix="szuflada" onNavigate={close} />
          </div>
        </div>
      ) : null}
    </>
  );
}

function useCollapsed() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem("sidebar-collapsed") === "true";
    } catch {
      return false;
    }
  });

  function toggle() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("sidebar-collapsed", String(next));
      } catch {
        // localStorage not available
      }
      return next;
    });
  }

  return { collapsed, toggle };
}

export function AppSidebar() {
  const { t } = useTranslation();
  const { collapsed, toggle } = useCollapsed();

  return (
    <>
      <MobileBar />
      <aside
        aria-label={t("sidebar.menuLabel")}
        className={cx(
          "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-line bg-subtle transition-[width] duration-200 lg:flex",
          collapsed ? "w-14" : "w-72",
        )}
      >
        <SidebarContent idPrefix="boczny" collapsed={collapsed} />
        <button
          type="button"
          onClick={toggle}
          title={collapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          className="absolute -right-3 top-6 z-10 grid size-6 place-items-center border border-line bg-subtle text-ink shadow-sm hover:bg-surface"
        >
          {collapsed ? (
            <ChevronRight aria-hidden="true" className="size-3.5" />
          ) : (
            <ChevronLeft aria-hidden="true" className="size-3.5" />
          )}
          <span className="sr-only">
            {collapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          </span>
        </button>
      </aside>
    </>
  );
}
