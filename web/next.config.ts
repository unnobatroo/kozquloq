import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export keeps the demo deployable anywhere; Supabase env vars
  // switch the data source to a live Postgres-backed report feed.
  output: "export",
};

export default nextConfig;
