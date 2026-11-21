import {
  Archive,
  CloudOff,
  EyeOff,
  History,
  ImageOff,
  Info,
  Scissors,
  SearchX,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";
import { Notice } from "@/components/ui/Notice";
import type { Warning, WarningCode } from "@/lib/types";

const ICONS: Record<WarningCode, LucideIcon> = {
  injection_detected: ShieldAlert,
  archival_material: Archive,
  source_status: CloudOff,
  incident_match: History,
  pii_masked: EyeOff,
  retrieval_degraded: SearchX,
  image_limits: ImageOff,
  input_truncated: Scissors,
};

const PROMINENT_TITLES: Partial<Record<WarningCode, string>> = {
  injection_detected: "Uwaga dotycząca bezpieczeństwa",
  source_status: "Uwaga dotycząca źródeł",
};

export function Warnings({ warnings }: { warnings: Warning[] }) {
  if (warnings.length === 0) return null;

  return (
    <ul aria-label="Uwagi do tego sprawdzenia" className="space-y-2">
      {warnings.map((warning, index) => {
        const title = PROMINENT_TITLES[warning.code];
        return (
          <li key={`${warning.code}-${index}`}>
            <Notice
              tone={title ? "warn" : "neutral"}
              icon={ICONS[warning.code] ?? Info}
              title={title}
              className={title ? "border-l-4" : undefined}
            >
              <p>{warning.message}</p>
            </Notice>
          </li>
        );
      })}
    </ul>
  );
}
