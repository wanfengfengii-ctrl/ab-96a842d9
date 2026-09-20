import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During local development Vite proxies /api and /healthz to the API
// container (or a locally running uvicorn). In production the built static
// files are served by nginx, which performs the same reverse proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY ?? "http://localhost:8000",
        changeOrigin: true,
      },
      "/healthz": {
        target: process.env.VITE_API_PROXY ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
