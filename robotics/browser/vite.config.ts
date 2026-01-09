import { defineConfig } from "vite";

export default defineConfig({
  build: {
    target: "esnext",
    outDir: "dist",
  },
  optimizeDeps: {
    exclude: ["oxigraph"],
  },
  server: {
    port: 3000,
  },
});
