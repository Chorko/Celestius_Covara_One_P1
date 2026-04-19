import Link from "next/link";
import { getMobileDownloadLinks } from "@/lib/mobileDownload";

export const metadata = {
  title: "Download Covara Worker Mobile",
};

function ctaClass(isEnabled: boolean): string {
  if (isEnabled) {
    return "rounded-lg px-4 py-3 text-sm font-semibold transition hover:opacity-90";
  }

  return "rounded-lg px-4 py-3 text-sm font-semibold opacity-50 cursor-not-allowed";
}

export default function DownloadPage() {
  const links = getMobileDownloadLinks();

  return (
    <main className="min-h-screen p-6 md:p-10" style={{ background: "var(--bg-primary)" }}>
      <div className="mx-auto max-w-2xl card-elevated p-6 md:p-8 space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Get the Covara Worker Mobile App
          </h1>
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            Pick your platform below. These links are controlled by your deployment environment.
          </p>
        </div>

        <div className="grid gap-3">
          {links.androidUrl ? (
            <a
              href={links.androidUrl}
              target="_blank"
              rel="noreferrer"
              className={ctaClass(true)}
              style={{ background: "var(--accent)", color: "white" }}
            >
              Download for Android
            </a>
          ) : (
            <div className={ctaClass(false)} style={{ background: "var(--bg-tertiary)", color: "var(--text-tertiary)" }}>
              Android link not configured
            </div>
          )}

          {links.iosUrl ? (
            <a
              href={links.iosUrl}
              target="_blank"
              rel="noreferrer"
              className={ctaClass(true)}
              style={{ background: "var(--info)", color: "white" }}
            >
              Download for iOS
            </a>
          ) : (
            <div className={ctaClass(false)} style={{ background: "var(--bg-tertiary)", color: "var(--text-tertiary)" }}>
              iOS link not configured
            </div>
          )}

          {links.webUrl ? (
            <a
              href={links.webUrl}
              target="_blank"
              rel="noreferrer"
              className={ctaClass(true)}
              style={{ background: "var(--bg-secondary)", color: "var(--text-primary)", border: "1px solid var(--border-primary)" }}
            >
              Open Expo / Web Install Link
            </a>
          ) : null}

          <Link
            href="/download/go"
            className={ctaClass(true)}
            style={{ background: "var(--accent)", color: "white" }}
          >
            Smart device redirect
          </Link>
        </div>

        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          Tip: share this page publicly from your site menu or marketing CTA so users always get the latest build links.
        </p>
      </div>
    </main>
  );
}
