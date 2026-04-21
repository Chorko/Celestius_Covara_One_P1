import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Manrope, Space_Grotesk } from "next/font/google";
import "./globals.css";
import "leaflet/dist/leaflet.css";

const manrope = Manrope({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  display: "swap",
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export const metadata: Metadata = {
  title: "Covara One — Parametric Income Protection",
  description:
    "AI-powered parametric income-protection platform for gig workers",
};

import { Analytics } from "@vercel/analytics/next";
import { PreloadWrapper } from "./PreloadWrapper";
import ThemeProvider from "@/components/ThemeProvider";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <body
        className={`${manrope.variable} ${ibmPlexMono.variable} ${spaceGrotesk.variable} antialiased w-full min-w-full`}
      >
        <ThemeProvider>
          <PreloadWrapper>{children}</PreloadWrapper>
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  );
}
