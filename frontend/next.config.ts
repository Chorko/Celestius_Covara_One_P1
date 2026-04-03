import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for Docker multi-stage build (copies .next/standalone)
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/:path*',
      },
    ]
  },
};

export default nextConfig;
