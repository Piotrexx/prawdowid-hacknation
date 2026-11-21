import Link from "next/link";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import { formatTime } from "@/lib/format";
import { checkPath } from "@/lib/links";
import type { SmsMessage } from "@/lib/types";
import { Linkified } from "./Linkified";

interface BubbleFrameProps {
  direction: SmsMessage["direction"];
  footer?: ReactNode;
  children: ReactNode;
}

export function BubbleFrame({ direction, footer, children }: BubbleFrameProps) {
  const incoming = direction === "in";
  return (
    <li className={cx("flex flex-col", incoming ? "items-end" : "items-start")}>
      <div
        className={cx(
          "max-w-[85%] rounded-2xl px-3.5 py-2 break-words whitespace-pre-wrap",
          incoming
            ? "rounded-br-sm bg-accent text-on-accent"
            : "rounded-bl-sm border border-line bg-subtle text-ink",
        )}
      >
        <span className="sr-only">{incoming ? "Ty: " : "Prawdowid: "}</span>
        {children}
      </div>
      {footer ? <p className="mt-0.5 px-1 text-sm text-muted">{footer}</p> : null}
    </li>
  );
}

export function SmsBubble({ message }: { message: SmsMessage }) {
  const incoming = message.direction === "in";
  const path = message.check_id ? checkPath(message.check_id) : null;
  const linkAlreadyInBody = path !== null && message.body.includes(path);

  return (
    <BubbleFrame direction={message.direction} footer={formatTime(message.created_at)}>
      <Linkified
        text={message.body}
        linkClassName={incoming ? "underline underline-offset-2" : "link"}
      />
      {path && !incoming && !linkAlreadyInBody ? (
        <Link
          href={path}
          target="_blank"
          className="link mt-1 flex min-h-11 items-center font-medium"
        >
          Zobacz pełny wynik
          <span className="sr-only"> (otwiera się w nowej karcie)</span>
        </Link>
      ) : null}
    </BubbleFrame>
  );
}
