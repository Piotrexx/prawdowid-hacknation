import { useRouter } from "next/navigation";
import { requestNewCheck } from "@/lib/newCheck";
import { resetConversation } from "./conversationStore";

/** Starts a fresh conversation from any page: clears the thread, cancels running checks, opens the chat. */
export function useStartNewSession(onNavigate?: () => void) {
  const router = useRouter();
  return () => {
    resetConversation();
    requestNewCheck();
    if (window.location.pathname !== "/") router.push("/");
    onNavigate?.();
  };
}
