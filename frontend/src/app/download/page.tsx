import { Apple, ArrowUpRight, Download, Rocket, ShieldCheck, Sparkles, Smartphone } from "lucide-react";
import { getMobileDownloadLinks } from "@/lib/mobileDownload";

export const metadata = {
  title: "Download Covara Worker Mobile",
};

function ctaClass(isEnabled: boolean): string {
  if (isEnabled) {
    return "group rounded-2xl px-5 py-5 text-sm font-semibold transition duration-300 ease-out hover:-translate-y-1 hover:shadow-xl";
  }

  return "rounded-2xl px-5 py-5 text-sm font-semibold opacity-55 cursor-not-allowed";
}

function hostLabel(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.host;
  } catch {
    return "External link";
  }
}

function webLinkLooksMisconfigured(url: string): boolean {
  try {
    const host = new URL(url).host.toLowerCase();
    return host.includes("covara-one.vercel.app") || host.includes("localhost");
  } catch {
    return true;
  }
}

export default function DownloadPage() {
  const links = getMobileDownloadLinks();
  const webLinkMisconfigured = links.webUrl ? webLinkLooksMisconfigured(links.webUrl) : false;
  const hasConfiguredLink = Boolean(links.androidUrl || links.iosUrl || links.webUrl);

  return (
    <main
      className="relative min-h-screen overflow-hidden p-6 md:p-10"
      style={{
        background:
          "radial-gradient(circle at 12% 10%, color-mix(in srgb, var(--accent) 24%, transparent), transparent 42%), radial-gradient(circle at 88% 16%, color-mix(in srgb, var(--info) 16%, transparent), transparent 34%), var(--bg-primary)",
      }}
    >
      <div
        className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full blur-3xl"
        style={{ background: "color-mix(in srgb, var(--accent) 28%, transparent)" }}
      />
      <div
        className="pointer-events-none absolute -right-20 top-1/3 h-72 w-72 rounded-full blur-3xl"
        style={{ background: "color-mix(in srgb, var(--info) 22%, transparent)" }}
      />

      <div className="relative mx-auto max-w-4xl space-y-5">
        <div className="card-elevated p-6 md:p-8 space-y-6 animate-fade-in-up" style={{ border: "1px solid var(--border-primary)" }}>
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold" style={{ background: "var(--accent-muted)", color: "var(--accent)" }}>
                <Sparkles size={14} /> Mobile Distribution Hub
              </span>
              <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold" style={{ background: "var(--success-muted)", color: "var(--success)" }}>
                <ShieldCheck size={14} /> Judge Ready
              </span>
            </div>

            <h1 className="text-3xl md:text-4xl font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>
              Download Covara Worker App
            </h1>
            <p className="text-sm md:text-base max-w-2xl" style={{ color: "var(--text-tertiary)" }}>
              Fast path for demos: use direct APK for Android and Open Expo for build visibility. Cards below animate in and open exact configured targets.
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-xl p-3 animate-fade-in-up delay-100" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-primary)" }}>
              <p className="text-[11px] uppercase tracking-wider font-mono" style={{ color: "var(--text-tertiary)" }}>Android</p>
              <p className="mt-1 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Direct APK Install</p>
            </div>
            <div className="rounded-xl p-3 animate-fade-in-up delay-200" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-primary)" }}>
              <p className="text-[11px] uppercase tracking-wider font-mono" style={{ color: "var(--text-tertiary)" }}>Open Expo</p>
              <p className="mt-1 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Build Page Landing</p>
            </div>
            <div className="rounded-xl p-3 animate-fade-in-up delay-300" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-primary)" }}>
              <p className="text-[11px] uppercase tracking-wider font-mono" style={{ color: "var(--text-tertiary)" }}>Experience</p>
              <p className="mt-1 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Motion + Icon Driven</p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {links.androidUrl ? (
              <a
                href={links.androidUrl}
                target="_blank"
                rel="noreferrer"
                className={`${ctaClass(true)} animate-fade-in-up delay-200`}
                style={{
                  background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 58%, #1e40af 100%)",
                  color: "white",
                  border: "1px solid rgba(147, 197, 253, 0.35)",
                }}
              >
                <span className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-lg" style={{ background: "rgba(255,255,255,0.18)" }}>
                  <Download size={18} />
                </span>
                <span className="flex items-center justify-between gap-3">
                  <span className="text-base font-semibold">
                    Download Android APK
                  </span>
                  <ArrowUpRight size={16} className="transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                </span>
                <span className="mt-2 block text-xs opacity-90">Direct install link for Android devices</span>
                <span className="mt-2 block text-[11px] font-mono opacity-75">{hostLabel(links.androidUrl)}</span>
              </a>
            ) : (
              <div
                className={`${ctaClass(false)} animate-fade-in-up delay-200`}
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
                className={`${ctaClass(true)} animate-fade-in-up delay-300`}
                style={{
                  background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
                  color: "white",
                  border: "1px solid rgba(148, 163, 184, 0.35)",
                }}
              >
                <span className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-lg" style={{ background: "rgba(255,255,255,0.14)" }}>
                  <Apple size={18} />
                </span>
                <span className="flex items-center justify-between gap-3">
                  <span className="text-base font-semibold">
                    Download for iOS
                  </span>
                  <ArrowUpRight size={16} className="transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                </span>
                <span className="mt-2 block text-xs opacity-90">App Store / TestFlight destination</span>
                <span className="mt-2 block text-[11px] font-mono opacity-75">{hostLabel(links.iosUrl)}</span>
              </a>
            ) : (
              <div
                className={`${ctaClass(false)} animate-fade-in-up delay-300`}
                style={{ background: "var(--bg-tertiary)", color: "var(--text-tertiary)", border: "1px dashed var(--border-primary)" }}
              >
                <span className="flex items-center gap-2">
                  <Apple size={16} /> iOS link not configured
                </span>
              </div>
            )}
          </div>

          <div className="grid gap-3">
            {links.webUrl && !webLinkMisconfigured ? (
              <a
                href={links.webUrl}
                target="_blank"
                rel="noreferrer"
                className={`${ctaClass(true)} animate-fade-in-up delay-400`}
                style={{
                  background: "color-mix(in srgb, var(--info) 20%, var(--bg-secondary))",
                  color: "var(--text-primary)",
                  border: "1px solid color-mix(in srgb, var(--info) 40%, transparent)",
                }}
              >
                <span className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-lg" style={{ background: "color-mix(in srgb, var(--info) 22%, transparent)" }}>
                  <Rocket size={18} />
                </span>
                <span className="flex items-center justify-between gap-3">
                  <span className="text-base font-semibold flex items-center gap-2">
                    <Smartphone size={16} /> Open Expo / Web Install Link
                  </span>
                  <ArrowUpRight size={16} className="transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                </span>
                <span className="mt-2 block text-xs" style={{ color: "var(--text-tertiary)" }}>
                  Destination: {hostLabel(links.webUrl)}
                </span>
              </a>
            ) : links.webUrl ? (
              <div
                className={`${ctaClass(false)} animate-fade-in-up delay-400`}
                style={{
                  background: "color-mix(in srgb, var(--warning) 14%, var(--bg-secondary))",
                  color: "var(--text-primary)",
                  border: "1px solid color-mix(in srgb, var(--warning) 45%, transparent)",
                }}
              >
                <span className="flex items-center gap-2">
                  <Smartphone size={16} /> Open Expo / Web Install Link (misconfigured)
                </span>
                <span className="mt-2 block text-xs" style={{ color: "var(--warning)" }}>
                  Current value points to {hostLabel(links.webUrl)}. Set NEXT_PUBLIC_MOBILE_DOWNLOAD_WEB_URL to your Expo/TestFlight URL.
                </span>
              </div>
            ) : null}

          </div>

          {!hasConfiguredLink ? (
            <div className="rounded-xl p-4 animate-fade-in-up delay-500" style={{ background: "var(--danger-muted)", border: "1px solid var(--danger)", color: "var(--danger)" }}>
              No download links are configured yet. Add mobile distribution URLs in deployment env vars first.
            </div>
          ) : null}
        </div>

        <p className="text-xs px-2 animate-fade-in-up delay-500" style={{ color: "var(--text-tertiary)" }}>
          Tip: keep Android/iOS/Web URLs updated in deployment env vars so these buttons always point to current builds.
        </p>
      </div>
    </main>
  );
}
