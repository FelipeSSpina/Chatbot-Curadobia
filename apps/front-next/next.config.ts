import type { NextConfig } from "next";

const API_DEST = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/webapi/:path*",   destination: `${API_DEST}/:path*` },
      { source: "/apps/web/:path*", destination: "/legacy/:path*"     },
    ];
  },
};

export default nextConfig;