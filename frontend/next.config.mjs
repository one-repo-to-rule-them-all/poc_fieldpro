/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // typedRoutes is disabled for the public demo: the dashboard pages have
  // several pre-existing Link/router.push targets that don't resolve to real
  // routes (e.g. router.push(`/locations/${id}`) — no detail page exists).
  // Re-enable + clean those up in a follow-up; runtime behavior is identical.
  experimental: { typedRoutes: false },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.r2.cloudflarestorage.com" },
    ],
  },
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME || "FieldPro",
  },
};

export default nextConfig;
