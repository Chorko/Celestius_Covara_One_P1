import Link from "next/link";
import { Apple, ArrowUpRight, Download, Sparkles, Smartphone } from "lucide-react";
import { getMobileDownloadLinks } from "@/lib/mobileDownload";

export const metadata = {
  title: "Download Covara Worker Mobile",
};

function ctaClass(isEnabled: boolean): string {
  if (isEnabled) {
    return "group rounded-xl px-4 py-4 text-sm font-semibold transition duration-200 hover:-translate-y-0.5";
  }

  return "rounded-xl px-4 py-4 text-sm font-semibold opacity-55 cursor-not-allowed";
}

function hostLabel(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.host;
  } catch {
    return "External link";
  }
}

export default function DownloadPage() {
  const links = getMobileDownloadLinks();

  return (
    <main
      className="min-h-screen p-6 md:p-10"
      style={{
        background:
          "radial-gradient(circle at top, color-mix(in srgb, var(--accent) 22%, transparent), transparent 42%), var(--bg-primary)",
      }}
    >
      <div className="mx-auto max-w-3xl space-y-5">
        <div className="card-elevated p-6 md:p-8 space-y-6" style={{ border: "1px solid var(--border-primary)" }}>
          <div className="space-y-2">
            <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold" style={{ background: "var(--accent-muted)", color: "var(--accent)" }}>
              <Sparkles size={14} /> Mobile Distribution
            </span>
            <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Get the Covara Worker Mobile App
            </h1>
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Choose how you want to install. Smart redirect now auto-routes to a working destination and avoids landing-page loops.
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {links.androidUrl ? (
              <a
                href={links.androidUrl}
                target="_blank"
                rel="noreferrer"
                className={ctaClass(true)}
                style={{
                  background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 58%, #1e40af 100%)",
                  color: "white",
                  border: "1px solid rgba(147, 197, 253, 0.35)",
                }}
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2">
                    <Download size={16} /> Download Android APK
                  </span>
                  <ArrowUpRight size={16} />
                </span>
                <span className="mt-2 block text-xs opacity-90">Direct install link for Android devices</span>
              </a>
            ) : (
              <div
                className={ctaClass(false)}
                style={{ background: "var(--bg-tertiary)", color: "var(--text-tertiary)", border: "1px dashed var(--border-primary)" }}
              >
                <span className="flex items-center gap-2">
                  <Download size={16} /> Android APK link not configured
                </span>
              </div>
            )}

            {links.iosUrl ? (
              <a
                href={links.iosUrl}
                target="_blank"
                rel="noreferrer"
                className={ctaClass(true)}
                style={{
                  background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
                  color: "white",
                  border: "1px solid rgba(148, 163, 184, 0.35)",
                }}
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2">
                    <Apple size={16} /> Download for iOS
                  </span>
                  <ArrowUpRight size={16} />
                </span>
                <span className="mt-2 block text-xs opacity-90">App Store / TestFlight destination</span>
              </a>
            ) : (
              <div
                className={ctaClass(false)}
                style={{ background: "var(--bg-tertiary)", color: "var(--text-tertiary)", border: "1px dashed var(--border-primary)" }}
              >
                <span className="flex items-center gap-2">
                  <Apple size={16} /> iOS link not configured
                </span>
              </div>
            )}
          </div>

          <div className="grid gap-3">
            {links.webUrl ? (
              <a
                href={links.webUrl}
                target="_blank"
                rel="noreferrer"
                className={ctaClass(true)}
                style={{
                  background: "color-mix(in srgb, var(--info) 20%, var(--bg-secondary))",
                  color: "var(--text-primary)",
                  border: "1px solid color-mix(in srgb, var(--info) 40%, transparent)",
                }}
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2">
                    <Smartphone size={16} /> Open Expo / Web Install Link
                  </span>
                  <ArrowUpRight size={16} />
                </span>
                <span className="mt-2 block text-xs" style={{ color: "var(--text-tertiary)" }}>
                  Destination: {hostLabel(links.webUrl)}
                </span>
              </a>
            ) : null}

            <Link
              href="/download/go"
              className={ctaClass(true)}
              style={{
                background: "linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)",
                color: "white",
                border: "1px solid rgba(56, 189, 248, 0.35)",
              }}
            >
              <span className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2">
                  <Smartphone size={16} /> Smart Device Redirect
                </span>
                <ArrowUpRight size={16} />
              </span>
              <span className="mt-2 block text-xs opacity-90">
                Auto-detects device; if a target loops back here, fallback routing kicks in.
              </span>
            </Link>
          </div>
        </div>

        <p className="text-xs px-2" style={{ color: "var(--text-tertiary)" }}>
          Tip: keep Android/iOS/Web URLs updated in deployment env vars so these buttons always point to current builds.
        </p>
      </div>
    </main>
  );
}
