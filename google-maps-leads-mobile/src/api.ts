import { CreateJobPayload, Lead, LeadStatus, Metrics, ScrapeJob } from "./types";

const cleanBase = (baseUrl: string) => baseUrl.replace(/\/+$/, "");

async function requestJson<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${cleanBase(baseUrl)}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}${body ? `: ${body}` : ""}`);
  }
  return (await response.json()) as T;
}

export const LeadsApi = {
  metrics(baseUrl: string) {
    return requestJson<Metrics>(baseUrl, "/google-maps-leads/api/metrics");
  },
  leads(baseUrl: string, options: { q?: string; status?: string; phoneOnly?: boolean } = {}) {
    const params = new URLSearchParams();
    if (options.q) params.set("q", options.q);
    if (options.status) params.set("status", options.status);
    if (options.phoneOnly) params.set("phone_only", "true");
    const query = params.toString();
    return requestJson<Lead[]>(baseUrl, `/google-maps-leads/api/leads${query ? `?${query}` : ""}`);
  },
  jobs(baseUrl: string) {
    return requestJson<ScrapeJob[]>(baseUrl, "/google-maps-leads/api/jobs");
  },
  createJob(baseUrl: string, payload: CreateJobPayload) {
    return requestJson<ScrapeJob>(baseUrl, "/google-maps-leads/api/jobs", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  updateLeadStatus(baseUrl: string, leadId: string, status: LeadStatus) {
    return requestJson<Lead>(baseUrl, `/google-maps-leads/api/leads/${leadId}`, {
      method: "PATCH",
      body: JSON.stringify({ status })
    });
  },
  exportCsvUrl(baseUrl: string, phoneOnly = true) {
    return `${cleanBase(baseUrl)}/google-maps-leads/export.csv${phoneOnly ? "?phone_only=true" : ""}`;
  },
  webUrl(baseUrl: string) {
    return `${cleanBase(baseUrl)}/google-maps-leads`;
  }
};
