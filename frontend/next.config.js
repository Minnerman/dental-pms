/** @type {import('next').NextConfig} */
const backendBaseUrl = (process.env.BACKEND_BASE_URL || "http://backend:8000").replace(/\/$/, "");

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendBaseUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
