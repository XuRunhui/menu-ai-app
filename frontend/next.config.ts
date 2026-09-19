import type { NextConfig } from "next";

// Where the Next.js server forwards /api/* and /dish-images/* requests.
// Local dev: uvicorn on :8000. Single-container deploy: uvicorn bound to 127.0.0.1:8000.
const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

const nextConfig: NextConfig = {
  // Self-contained server bundle (server.js + minimal node_modules) for the Docker image.
  output: 'standalone',
  experimental: {
    // LLM menu parsing + knowledge-base builds can exceed the 30s proxy default.
    proxyTimeout: 180_000,
    // Phone photos of menus can be larger than the 10MB default.
    proxyClientMaxBodySize: '20mb',
  },
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${BACKEND_URL}/api/:path*` },
      { source: '/dish-images/:path*', destination: `${BACKEND_URL}/dish-images/:path*` },
    ];
  },
};

export default nextConfig;
