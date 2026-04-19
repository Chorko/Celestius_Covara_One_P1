import { NextRequest, NextResponse } from "next/server";
import { getMobileDownloadLinks, resolveDownloadTarget } from "@/lib/mobileDownload";

export const dynamic = "force-dynamic";

function normalizeTarget(target: string, requestUrl: string): string | null {
  const trimmed = target.trim();
  if (!trimmed) {
    return null;
  }

  try {
    const request = new URL(requestUrl);
    const resolved = new URL(trimmed, request);
    const sameOrigin = resolved.origin === request.origin;

    // Download targets should be external app-distribution destinations.
    if (sameOrigin) {
      return null;
    }

    return resolved.toString();
  } catch {
    return null;
  }
}

export function GET(request: NextRequest): NextResponse {
  const links = getMobileDownloadLinks();
  const platform = request.nextUrl.searchParams.get("platform");
  const userAgent = request.headers.get("user-agent");
  const preferred = resolveDownloadTarget(links, platform, userAgent);

  const candidates = [preferred, links.webUrl, links.androidUrl, links.iosUrl, links.fallbackUrl]
    .map((candidate) => normalizeTarget(candidate, request.url))
    .filter((candidate): candidate is string => Boolean(candidate));

  const target = candidates[0];

  if (!target) {
    const fallback = new URL("/download?unavailable=1", request.url);
    return NextResponse.redirect(fallback, { status: 302 });
  }

  return NextResponse.redirect(target, { status: 302 });
}
