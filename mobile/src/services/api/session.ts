import { getMobileEnv } from "../../config/env";
import { HttpRequestError, type ApiErrorBody } from "./http";

export type MobileRole = "worker" | "insurer_admin" | null;

export interface AuthMeResponse {
  id: string;
  email: string | null;
  role: MobileRole;
  profile: Record<string, unknown> | null;
  needs_onboarding: boolean;
}

export interface WorkerProfileResponse {
  profile_id: string;
  aadhaar_verified?: boolean;
  bank_verified?: boolean;
  phone_verified?: boolean;
  face_verified?: boolean;
  [key: string]: unknown;
}

function trimTrailingSlash(input: string): string {
  return input.endsWith("/") ? input.slice(0, -1) : input;
}

async function getJson<TResponse>(
  url: string,
  headers: Record<string, string>,
): Promise<TResponse> {
  const response = await fetch(url, {
    method: "GET",
    headers,
  });

  const rawText = await response.text();
  let parsed: ApiErrorBody | TResponse | null = null;

  if (rawText) {
    try {
      parsed = JSON.parse(rawText) as ApiErrorBody | TResponse;
    } catch {
      parsed = { detail: rawText };
    }
  }

  if (!response.ok) {
    const detail =
      typeof parsed === "object" && parsed && "detail" in parsed
        ? String((parsed as ApiErrorBody).detail ?? "request_failed")
        : `HTTP_${response.status}`;

    throw new HttpRequestError(
      `Request failed with status ${response.status}`,
      response.status,
      detail,
      (parsed as ApiErrorBody) ?? null,
    );
  }

  return (parsed as TResponse) ?? ({} as TResponse);
}

function authHeaders(accessToken: string): Record<string, string> {
  return {
    Authorization: `Bearer ${accessToken}`,
    Accept: "application/json",
  };
}

export async function fetchAuthMe(accessToken: string): Promise<AuthMeResponse> {
  const env = getMobileEnv();
  const baseUrl = trimTrailingSlash(env.apiBaseUrl);
  return getJson<AuthMeResponse>(`${baseUrl}/auth/me`, authHeaders(accessToken));
}

export async function fetchWorkerProfile(
  accessToken: string,
): Promise<WorkerProfileResponse> {
  const env = getMobileEnv();
  const baseUrl = trimTrailingSlash(env.apiBaseUrl);
  return getJson<WorkerProfileResponse>(`${baseUrl}/workers/me`, authHeaders(accessToken));
}
