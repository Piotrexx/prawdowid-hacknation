import { useSyncExternalStore } from "react";
import { SIDEBAR_STORAGE_KEY as STORAGE_KEY } from "./sidebarScript";

/**
 * Collapsed desktop sidebar. The state lives on <html data-sidebar>, so CSS can style the rail
 * before React hydrates and a saved choice never flashes open.
 */
const listeners = new Set<() => void>();

function isCollapsed(): boolean {
  return document.documentElement.dataset.sidebar === "collapsed";
}

export function setSidebarCollapsed(collapsed: boolean): void {
  const root = document.documentElement;
  if (collapsed) root.dataset.sidebar = "collapsed";
  else delete root.dataset.sidebar;
  try {
    if (collapsed) window.localStorage.setItem(STORAGE_KEY, "collapsed");
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Still collapses for this visit when storage is blocked.
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useSidebarCollapsed(): boolean {
  return useSyncExternalStore(subscribe, isCollapsed, () => false);
}
