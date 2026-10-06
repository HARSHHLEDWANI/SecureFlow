import type { NextConfig } from "next";

// Optional same-site API proxy. Set API_PROXY_TARGET (e.g. https://secureflow-api.onrender.com)
// and NEXT_PUBLIC_API_URL=/api/v1 on the frontend host: the browser then talks to its own
// origin, so the httpOnly refresh cookie is first-party and survives browsers that block
// third-party cookies (Safari ITP, Chrome's phase-out). With a proxy, the backend can use
// REFRESH_COOKIE_SAMESITE=lax.
//
// Trade-off: the API then sees the frontend host's egress IPs, not end users, so per-IP rate
// limits become coarse unless that host's proxy ranges are added to the backend's
// TRUSTED_PROXIES. The WebSocket (/ws/alerts) cannot go through a rewrite and stays direct.
const apiProxyTarget = process.env.API_PROXY_TARGET?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactCompiler: true,
  async rewrites() {
    return apiProxyTarget
      ? [{ source: "/api/v1/:path*", destination: `${apiProxyTarget}/api/v1/:path*` }]
      : [];
  },
};

export default nextConfig;
