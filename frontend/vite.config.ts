import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  base: "/static/storefront/",
  build: {
    outDir: "../app/static/storefront",
    emptyOutDir: true,
    manifest: true,
    rollupOptions: { input: "src/main.tsx" },
  },
  test: { environment: "jsdom", include: ["src/**/*.test.tsx"] },
});
