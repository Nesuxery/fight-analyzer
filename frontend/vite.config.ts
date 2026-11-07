import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Ports come from scripts/launch.py (FA_API_PORT / FA_WEB_PORT).
const apiPort = process.env.FA_API_PORT ?? "8000";
const webPort = Number(process.env.FA_WEB_PORT ?? "5173");

export default defineConfig({
  plugins: [react()],
  server: {
    // Loopback only: the app and its videos stay on this computer.
    host: "127.0.0.1",
    port: webPort,
    strictPort: true,
    proxy: {
      "/api": { target: `http://127.0.0.1:${apiPort}`, changeOrigin: true },
    },
  },
  preview: { host: "127.0.0.1", port: webPort, strictPort: true },
});
