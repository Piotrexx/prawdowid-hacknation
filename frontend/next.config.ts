import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  async redirects() {
    // Stare, zapisane linki do wyników nadal działają po zmianie nazwy trasy.
    return [
      {
        source: "/sprawdzenie/:id",
        destination: "/analiza/:id",
        permanent: true,
      },
    ];
  },
  turbopack: {
    resolveAlias: {
      "sharp$": false,
      "onnxruntime-node$": false,
    },
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  webpack: (config) => {
    config.resolve.alias = { ...config.resolve.alias, "sharp$": false, "onnxruntime-node$": false };
    config.experiments = { ...config.experiments, asyncWebAssembly: true };
    return config;
  },
};

export default nextConfig;
