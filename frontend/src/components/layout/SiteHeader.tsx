"use client";

import { Menu, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useState } from "react";
import { AccessibilityMenu } from "@/components/a11y/AccessibilityMenu";
import { cx } from "@/lib/cx";

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
    <ul className="flex flex-col pb-2 md:flex-row md:gap-1 md:pb-0">
      {NAV_ITEMS.map((item) => {
        const current = isCurrent(pathname, item.href);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={current ? "page" : undefined}
              onClick={onNavigate}
              className={cx(
                // gov.pl marks the open section with a thick underline rather than a fill.
                "flex min-h-11 items-center border-b-[3px] px-3 hover:bg-white/10",
                current ? "border-current font-bold" : "border-transparent",
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
    <header className="gov-bar border-b border-bar-line bg-bar text-on-bar">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2">
        <Link
          href="/"
          onClick={close}
          className="mr-auto inline-flex min-h-11 items-center gap-2.5 text-xl font-bold tracking-tight md:order-1 md:mr-3"
        >
          {/* The full mascot art, transparent and uncropped, fixed regardless of theme. */}
          <Image
            src="/maskotka.png"
            alt=""
            aria-hidden="true"
            width={250}
            height={640}
            className="h-9 w-auto shrink-0 self-start"
          />
          Prawdowid
        </Link>

        {/* Kept outside the collapsible menu so it is reachable at every width. */}
        <div className="md:order-3">
          <AccessibilityMenu />
        </div>

        <button
          type="button"
          className="inline-flex min-h-11 items-center gap-2 rounded-sm border border-current px-3 font-semibold md:hidden"
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
          className={cx(
            "w-full md:order-2 md:mr-auto md:block md:w-auto",
            open ? "block" : "hidden",
          )}
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
