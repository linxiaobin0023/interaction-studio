import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:28741",
      "/health": "http://127.0.0.1:28741",
      "/docs": "http://127.0.0.1:28741",
      "/openapi.json": "http://127.0.0.1:28741",
    },
  },
});
