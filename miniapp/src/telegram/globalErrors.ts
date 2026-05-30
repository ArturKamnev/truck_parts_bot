export interface GlobalErrorSummary {
  message: string;
  source?: string;
  lineno?: number;
  colno?: number;
  stack?: string;
  reason?: string;
  timestamp: number;
}

let lastGlobalError: GlobalErrorSummary | null = null;

export const getLastGlobalError = (): GlobalErrorSummary | null => {
  if (lastGlobalError) return lastGlobalError;
  const cached = localStorage.getItem("tma_last_global_error");
  if (cached) {
    try {
      return JSON.parse(cached) as GlobalErrorSummary;
    } catch (e) {
      // ignore
    }
  }
  return null;
};

export const clearLastGlobalError = (): void => {
  lastGlobalError = null;
  localStorage.removeItem("tma_last_global_error");
};

if (typeof window !== "undefined") {
  window.onerror = (message, source, lineno, colno, error) => {
    const summary: GlobalErrorSummary = {
      message: String(message),
      source: source ? String(source) : undefined,
      lineno: lineno || undefined,
      colno: colno || undefined,
      stack: error?.stack ? String(error.stack) : undefined,
      timestamp: Date.now()
    };
    lastGlobalError = summary;
    
    // safe summary for prod vs dev
    const isDev = import.meta.env.DEV;
    const safeSummary = {
      ...summary,
      stack: isDev ? summary.stack : undefined
    };
    localStorage.setItem("tma_last_global_error", JSON.stringify(safeSummary));
  };

  window.onunhandledrejection = (event) => {
    const summary: GlobalErrorSummary = {
      message: "Unhandled promise rejection",
      reason: event.reason ? String(event.reason) : "unknown",
      stack: event.reason?.stack ? String(event.reason.stack) : undefined,
      timestamp: Date.now()
    };
    lastGlobalError = summary;
    
    const isDev = import.meta.env.DEV;
    const safeSummary = {
      ...summary,
      stack: isDev ? summary.stack : undefined
    };
    localStorage.setItem("tma_last_global_error", JSON.stringify(safeSummary));
  };
}
