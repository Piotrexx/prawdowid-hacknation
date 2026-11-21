import { Tag, Search } from "lucide-react";

interface KeywordsDisplayProps {
  keywords: string[];
}

export function KeywordsDisplay({ keywords }: KeywordsDisplayProps) {
  return (
    <section aria-labelledby="keywords-heading" className="space-y-3">
      <h3 id="keywords-heading" className="text-xl font-semibold flex items-center gap-2">
        <Search className="size-5" />
        Słowa kluczowe (model Bielik 4.5B)
      </h3>
      <div className="flex flex-wrap gap-2">
        {keywords.map((keyword, index) => (
          <span
            key={index}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/10 text-accent border border-accent/20 text-sm font-medium"
          >
            <Tag className="size-3.5" />
            {keyword}
          </span>
        ))}
      </div>
      <p className="text-sm text-muted">
        Słowa kluczowe wyekstrahowane automatycznie z tytułu i treści artykułu.
        Służą do wyszukiwania powiązanych sprawdzeń faktów.
      </p>
    </section>
  );
}