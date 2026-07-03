import type { NextConfig } from "next";
import path from "path";
import { loadEnvConfig } from "@next/env";

const monorepoRoot = path.join(__dirname, "..");
loadEnvConfig(monorepoRoot);

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: apiUrl,
  },
};

export default nextConfig;
