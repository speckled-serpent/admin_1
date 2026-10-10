const LABELS: Record<string, string> = {
  "system-health": "System health",
  performance: "Performance",
  logs: "Logs",
  "uptime-incidents": "Uptime & incidents",
  "deploys-releases": "Deploys/releases",
  "user-data": "User data",
  "sales-data": "Sales data",
  "consolidated-costs": "Consolidated costs",
  "product-metrics": "Product metrics",
  marketing: "Marketing",
  support: "Support",
  logistics: "Logistics",
};

export function labelFor(key: string): string {
  return LABELS[key] ?? key;
}
