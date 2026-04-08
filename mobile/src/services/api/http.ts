export interface ApiErrorBody {
  detail?: string;
  [key: string]: unknown;
}

export class HttpRequestError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail: string,
    public readonly body: ApiErrorBody | null,
  ) {
    super(message);
    this.name = "HttpRequestError";
  }
}

export async function postJson<TResponse>(
  url: string,
  body: unknown,
  headers: Record<string, string>,
): Promise<TResponse> {
  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
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
