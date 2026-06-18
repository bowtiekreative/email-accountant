/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Same-origin API proxy: the browser calls /api/* on the frontend, and the
  // Next server forwards to the backend (resolved at runtime from env, so the
  // image is portable — no API URL baked in at build time). Skipped if the
  // client is configured with an absolute NEXT_PUBLIC_API_BASE.
  async rewrites() {
    if (process.env.NEXT_PUBLIC_API_BASE) return [];
    const backend = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
