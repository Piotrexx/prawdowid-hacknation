import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t-4 border-accent bg-subtle">
      <div className="mx-auto max-w-5xl space-y-2 px-4 py-6 text-muted">
        <ul className="flex flex-wrap gap-x-6">
          <li>
            <Link href="/o-systemie" className="link inline-flex min-h-11 items-center">
              Jak to działa
            </Link>
          </li>
          <li>
            <Link href="/zrodla" className="link inline-flex min-h-11 items-center">
              Katalog źródeł
            </Link>
          </li>
        </ul>
      </div>
    </footer>
  );
}
