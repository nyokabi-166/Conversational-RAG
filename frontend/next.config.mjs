/** @type {import('next').NextConfig} */
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectDirectory = path.dirname(fileURLToPath(import.meta.url));
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  webpack(config) {
    config.resolve.alias["@"] = path.join(projectDirectory, "src");
    return config;
  },
};

export default nextConfig;
