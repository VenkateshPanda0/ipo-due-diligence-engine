/**
 * API key handling for deployments with authentication enabled.
 *
 * The key is kept in sessionStorage only (cleared when the tab closes) and is
 * never written to source, logs or URLs. In local single-user mode no key is needed.
 */
const KEY = "ipo-dd.api-key";

export function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setApiKey(value: string | null): void {
  try {
    if (value) window.sessionStorage.setItem(KEY, value);
    else window.sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable */
  }
}
