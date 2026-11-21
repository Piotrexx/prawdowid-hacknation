/** Kept apart from lib/sidebar.ts: the root layout (a server component) inlines this before paint. */
export const SIDEBAR_STORAGE_KEY = "prawdowid_sidebar";

export const SIDEBAR_SCRIPT = `(function(){try{if(localStorage.getItem(${JSON.stringify(
  SIDEBAR_STORAGE_KEY,
)})==="collapsed")document.documentElement.dataset.sidebar="collapsed";}catch(e){}})();`;
