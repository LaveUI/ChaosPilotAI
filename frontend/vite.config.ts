import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("/node_modules/recharts/") || id.includes("/node_modules/d3-")) return "charts";
          if (id.includes("/node_modules/@xyflow/") || id.includes("/node_modules/@reactflow/")) return "flow";
          if (id.includes("/node_modules/react-dom/") || id.includes("/node_modules/react/")) return "react";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
  },
});
