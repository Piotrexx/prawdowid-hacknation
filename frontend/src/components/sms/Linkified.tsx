import { safeHttpUrl, splitLinks } from "@/lib/links";

/** Plain text with http(s) addresses turned into links. Everything else stays text. */
export function Linkified({ text, linkClassName }: { text: string; linkClassName: string }) {
  return (
    <>
      {splitLinks(text).map((part, index) => {
        if (part.type === "text") return <span key={index}>{part.value}</span>;
        const href = safeHttpUrl(part.href);
        if (!href) return <span key={index}>{part.href}</span>;
        return (
          <a
            key={index}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className={linkClassName}
          >
            {part.href}
            <span className="sr-only"> (otwiera się w nowej karcie)</span>
          </a>
        );
      })}
    </>
  );
}
