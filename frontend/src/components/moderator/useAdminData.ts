import { ApiError } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

export interface AdminAccess {
  token: string;
  /** Called when the server rejects the token, so the panel can return to the prompt. */
  onUnauthorized: () => void;
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.kind === "unauthorized";
}

/** Runs an admin request and reports a rejected token before passing the error on. */
export async function guarded<T>(access: AdminAccess, request: Promise<T>): Promise<T> {
  try {
    return await request;
  } catch (error) {
    if (isUnauthorized(error)) access.onUnauthorized();
    throw error;
  }
}

export function useAdminData<T>(
  access: AdminAccess,
  key: string,
  load: (token: string, signal: AbortSignal) => Promise<T>,
) {
  return useLoad(key, (signal) => guarded(access, load(access.token, signal)));
}
