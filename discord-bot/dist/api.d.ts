import { Buffer } from "node:buffer";
export declare class BackendError extends Error {
}
export interface Warning {
    code: string;
    message: string;
}
export interface CheckResponse {
    id: string;
    channel: string;
    status: "completed" | "needs_clarification" | "out_of_scope" | "error";
    status_message: string | null;
    error_code: string | null;
    summary: string | null;
    verdict: string | null;
    verdict_label: string | null;
    confidence: number | null;
    justification: string | null;
    warnings: Warning[];
}
export declare function checkText(userId: string, text: string): Promise<CheckResponse>;
export declare function checkUrl(userId: string, url: string): Promise<CheckResponse>;
export declare function checkImage(userId: string, file: Buffer, filename: string, contentType: string): Promise<CheckResponse>;
//# sourceMappingURL=api.d.ts.map