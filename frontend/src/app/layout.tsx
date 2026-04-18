import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import "leaflet/dist/leaflet.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
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
        className={`${inter.variable} ${jetbrainsMono.variable} antialiased w-full min-w-full`}
      >
        <ThemeProvider>
          <PreloadWrapper>{children}</PreloadWrapper>
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  );
}
