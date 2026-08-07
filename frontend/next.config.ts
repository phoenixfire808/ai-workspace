import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  distDir: process.env.NEXT_DIST_DIR?.trim() || ".next",
  outputFileTracingRoot: path.join(__dirname, ".."),
};

export default nextConfig;
