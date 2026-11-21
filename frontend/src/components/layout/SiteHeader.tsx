"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useState } from "react";
import { cx } from "@/lib/cx";
import { Logo } from "./Logo";

const NAV_ITEMS = [
  { href: "/", label: "Sprawdź" },
  { href: "/zrodla", label: "Źródła" },
  { href: "/o-systemie", label: "Jak to działa" },
  { href: "/moderator", label: "Moderator" },
];

function isCurrent(pathname: string | null, href: string): boolean {
  if (pathname === null) return false;
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

interface NavListProps {
  pathname: string | null;
  onNavigate: () => void;
}

function NavList({ pathname, onNavigate }: NavListProps) {
  return (
    <ul className="flex flex-col py-2 md:flex-row md:gap-1 md:py-0">
      {NAV_ITEMS.map((item) => {
        const current = isCurrent(pathname, item.href);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={current ? "page" : undefined}
              onClick={onNavigate}
              className={cx(
                "flex min-h-11 items-center rounded-lg px-3 hover:bg-subtle",
                current
                  ? "font-semibold text-ink underline decoration-2 underline-offset-8"
                  : "text-muted hover:text-ink",
              )}
            >
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function CurrentNavList({ onNavigate }: { onNavigate: () => void }) {
  return <NavList pathname={usePathname()} onNavigate={onNavigate} />;
}

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 px-4 py-2">
        <Link
          href="/"
          onClick={close}
          className="inline-flex min-h-11 items-center gap-2.5 text-xl font-semibold tracking-tight text-ink"
        >
          <Logo />
          Prawdowid
          <span className="hidden rounded border border-line-strong px-1.5 py-0.5 text-xs font-medium tracking-normal text-muted sm:inline">
            prototyp
          </span>
        </Link>

        <button
          type="button"
          className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-line-strong px-3 font-medium md:hidden"
          aria-expanded={open}
          aria-controls="menu-glowne"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? (
            <X aria-hidden="true" className="size-5" />
          ) : (
            <Menu aria-hidden="true" className="size-5" />
          )}
          Menu
        </button>

        <nav
          id="menu-glowne"
          aria-label="Główna nawigacja"
          className={cx("w-full md:block md:w-auto", open ? "block" : "hidden")}
        >
          {/* On routes with a dynamic segment the pathname is unknown while prerendering. */}
          <Suspense fallback={<NavList pathname={null} onNavigate={close} />}>
            <CurrentNavList onNavigate={close} />
          </Suspense>
        </nav>
      </div>
    </header>
  );
}
