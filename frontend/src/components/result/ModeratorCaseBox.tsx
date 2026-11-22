import { Lightbulb, UserRoundCheck } from "lucide-react";
import { Notice } from "@/components/ui/Notice";
import { plural } from "@/lib/format";
import type { ModeratorCaseInfo } from "@/lib/types";

export function ModeratorCaseBox({ info }: { info: ModeratorCaseInfo }) {
  if (info.state === "recommended") {
    // A recommendation only: nothing was queued, so it must not look like a handed-over case.
    return (
      <div className="flex gap-3 rounded-lg border border-dashed border-line-strong p-4">
        <Lightbulb aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-muted" />
        <div className="space-y-1">
          <p className="font-semibold">Zalecenie</p>
          {info.message ? <p>{info.message}</p> : null}
          <p className="text-muted">
            To tylko zalecenie. To twierdzenie nie zostało przekazane moderatorowi.
          </p>
        </div>
      </div>
    );
  }

  if (info.state !== "created" && info.state !== "updated") return null;

  const occurrences = info.occurrences ?? 0;
  const title =
    info.case_id != null
      ? `Twierdzenie nr ${info.case_id} czeka na analizę przez człowieka`
      : "Twierdzenie czeka na analizę przez człowieka";

  return (
    <Notice tone="info" icon={UserRoundCheck} title={title}>
      <p>{info.message || "Ta treść trafiła do kolejki moderatora."}</p>
      {occurrences > 1 ? (
        <p className="text-muted">
          Podobne zgłoszenie pojawiło się już {occurrences}{" "}
          {plural(occurrences, "raz", "razy", "razy")}.
        </p>
      ) : null}
      {info.notified ? <p className="text-muted">Moderator dostał powiadomienie.</p> : null}
    </Notice>
  );
}
