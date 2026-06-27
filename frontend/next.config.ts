import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Proxy /api to the FastAPI backend during dev (set API_URL in .env.local)
  async rewrites() {
    const api = process.env.API_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};
export default withNextIntl(nextConfig);
