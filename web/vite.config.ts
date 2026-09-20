import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发态把 /api 与 /health 代理到 API 容器/进程；
// 生产态由 Web 容器内的 nginx 反代（见 nginx.conf）。
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: Number(process.env.WEB_PORT ?? 5173),
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
      "/health-api": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/health-api/, "/health"),
      },
    },
  },
});
