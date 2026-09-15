// Thin API client. All REST calls live here.
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8005";

export const API_BASE = BASE_URL;
export const WS_BASE = BASE_URL.replace(/^http/, "ws");

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("ppe_token");
}

export function saveToken(token: string) {
  localStorage.setItem("ppe_token", token);
}

export function clearToken() {
  localStorage.removeItem("ppe_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ---------- Auth ----------
export interface User {
  id: number;
  username: string;
  full_name: string;
  role: "admin" | "supervisor";
  site_id: number | null;
  is_active: boolean;
}

export async function login(username: string, password: string): Promise<{ access_token: string; user: User }> {
  return request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function getMe(): Promise<User> {
  return request("/api/auth/me");
}

// ---------- Sites ----------
export interface Site {
  id: number;
  name: string;
  location: string;
  is_active: boolean;
}

export async function getSites(): Promise<Site[]> {
  return request("/api/sites?active=true");
}

// ---------- Workers ----------
export interface Worker {
  id: number;
  employee_code: string;
  full_name: string;
  trade: string;
  site_id: number;
  is_active: boolean;
}

export async function getWorkers(site_id: number): Promise<Worker[]> {
  return request(`/api/workers?site_id=${site_id}&active=true`);
}

// ---------- Health ----------
export async function getHealth(): Promise<{ status: string; model_loaded: boolean; device: string }> {
  return fetch(`${BASE_URL}/health`).then((r) => r.json());
}

// ---------- Vehicle Scans ----------
export interface VehicleScan {
  id: number;
  created_at: string;
  vehicle_type: string;
  site: { id: number; name: string };
  scanned_by: { id: number; username: string; full_name: string };
  items: Record<string, string>;
  overall: string;
  has_snapshot: boolean;
  snapshot_url: string | null;
}

export async function getVehicleScans(params?: {
  site_id?: number;
  vehicle_type?: string;
  limit?: number;
}): Promise<{ items: VehicleScan[]; total: number }> {
  const qs = new URLSearchParams();
  if (params?.site_id) qs.set("site_id", String(params.site_id));
  if (params?.vehicle_type) qs.set("vehicle_type", params.vehicle_type);
  if (params?.limit) qs.set("limit", String(params.limit));
  return request(`/api/vehicle-scans?${qs}`);
}

// ---------- Safety Test ----------
export interface TestQuestion {
  id: number;
  text: string;
  options: {
    A: string;
    B: string;
    C: string;
    D: string;
  };
}

export interface TestAttempt {
  id: number;
  score: number;
  total: number;
  passed: boolean;
}

export async function getTestQuestions(workerId: number): Promise<TestQuestion[]> {
  return request(`/api/test/start/${workerId}`);
}

export async function submitTest(
  workerId: number,
  siteId: number,
  answers: { question_id: number; answer: string }[]
): Promise<TestAttempt> {
  return request("/api/test/submit", {
    method: "POST",
    body: JSON.stringify({ worker_id: workerId, site_id: siteId, answers }),
  });
}
