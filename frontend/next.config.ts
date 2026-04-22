import type { NextConfig } from "next";

const defaultApiTarget = process.env.VERCEL
  ? "https://covara-backend.onrender.com"
  : "http://127.0.0.1:8000";

const apiProxyTarget = (process.env.API_PROXY_TARGET || defaultApiTarget).replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Required for Docker multi-stage build (copies .next/standalone)
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${apiProxyTarget}/:path*`,
      },
    ]
  },
};

export default nextConfig;
