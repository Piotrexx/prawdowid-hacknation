import Link from "next/link";
import { PageShell } from "@/components/layout/PageShell";

export default function NotFound() {
  return (
    <PageShell
      title="Nie ma takiej strony"
      lead="Adres może być błędny albo strona została przeniesiona."
    >
      <Link
        href="/"
        className="inline-flex min-h-11 items-center rounded-lg bg-accent px-4 font-medium text-on-accent hover:bg-accent-hover"
      >
        Przejdź do sprawdzania informacji
      </Link>
    </PageShell>
  );
}
