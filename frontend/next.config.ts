import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // Local: proxy API to FastAPI. Production: Vercel services rewrites handle /api.
    if (process.env.NODE_ENV === "development") {
      return [
        {
          source: "/api/:path*",
          destination: "http://127.0.0.1:8000/api/:path*",
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
