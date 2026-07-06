const STORAGE_KEY = "kayfabe-ple-results-admin";
const ADMIN_PASSWORD = "151617";

export function isResultsAdmin(): boolean {
  if (typeof window === "undefined") return false;
  return sessionStorage.getItem(STORAGE_KEY) === "1";
}

export function unlockResultsAdmin(password: string): boolean {
  if (password.trim() !== ADMIN_PASSWORD) return false;
  sessionStorage.setItem(STORAGE_KEY, "1");
  return true;
}

export function lockResultsAdmin(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}
