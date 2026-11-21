import { Disclosure } from "@/components/ui/Disclosure";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { inputKindLabel } from "@/lib/labels";
import type { InputInfo } from "@/lib/types";

const INLINE_LIMIT = 280;

interface InputRecapProps {
  input: InputInfo;
  id: string;
  level?: 2 | 3;
}

export function InputRecap({ input, id, level = 3 }: InputRecapProps) {
  const Heading = level === 2 ? "h2" : "h3";
  const text = input.text.trim();
  const sameAsUrl = input.url !== null && text === input.url.trim();

  return (
    <section
      id={id}
      aria-labelledby={`${id}-tytul`}
      className="scroll-mt-6 border border-line bg-surface px-4.5 py-4"
    >
      <Heading id={`${id}-tytul`} className="font-bold">
        Sprawdzana treść
        <span className="font-normal text-muted"> ({inputKindLabel(input.kind).toLowerCase()})</span>
      </Heading>
      {input.title ? <p className="mt-1 font-semibold">{input.title}</p> : null}
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
