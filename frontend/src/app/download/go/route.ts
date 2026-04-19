import { NextRequest, NextResponse } from "next/server";
import { getMobileDownloadLinks, resolveDownloadTarget } from "@/lib/mobileDownload";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest): NextResponse {
  const links = getMobileDownloadLinks();
  const platform = request.nextUrl.searchParams.get("platform");
  const userAgent = request.headers.get("user-agent");
  const target = resolveDownloadTarget(links, platform, userAgent);

  if (!target) {
    const fallback = new URL("/download", request.url);
    return NextResponse.redirect(fallback, { status: 302 });
  }

  return NextResponse.redirect(target, { status: 302 });
}
