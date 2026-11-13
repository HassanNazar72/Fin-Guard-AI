import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";
const apiDevUrl = process.env.API_DEV_URL ?? "http://127.0.0.1:8000";

const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  devIndicators: false,

  // Local development: proxy /api/* to the FastAPI server (uvicorn on :8000).
  // On Vercel, vercel.json routes /api/* to the Python serverless function.
  async rewrites() {
    if (!isDev) return [];
    return [{ source: "/api/:path*", destination: `${apiDevUrl}/api/:path*` }];
  },

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
