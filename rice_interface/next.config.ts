import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  // allowedDevOrigins: ['*'],
  logging: {
    incomingRequests: false,
  },
};

export default nextConfig;
