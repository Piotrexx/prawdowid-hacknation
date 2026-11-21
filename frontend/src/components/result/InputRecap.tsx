import { useId } from "react";
import { Disclosure } from "@/components/ui/Disclosure";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { inputKindLabel } from "@/lib/labels";
import type { InputInfo } from "@/lib/types";

const INLINE_LIMIT = 280;

export function InputRecap({ input }: { input: InputInfo }) {
  const headingId = useId();
  const text = input.text.trim();
  const sameAsUrl = input.url !== null && text === input.url.trim();

  return (
    <section
      aria-labelledby={headingId}
      className="rounded-lg border border-line bg-subtle px-4 py-3"
    >
      <h3 id={headingId} className="font-semibold">
        Sprawdzana treść
        <span className="font-normal text-muted"> ({inputKindLabel(input.kind).toLowerCase()})</span>
      </h3>
      {input.title ? <p className="mt-1 font-medium">{input.title}</p> : null}
      {input.url ? (
        <p className="mt-1">
          <ExternalLink href={input.url} className="inline-block py-2 break-all">
            {input.url}
          </ExternalLink>
        </p>
      ) : null}
      {text && !sameAsUrl ? (
        text.length <= INLINE_LIMIT ? (
          <p className="mt-1 whitespace-pre-line">{text}</p>
        ) : (
          <Disclosure summary="Pokaż całą treść">
            <p className="whitespace-pre-line">{text}</p>
          </Disclosure>
        )
      ) : null}
    </section>
  );
}
