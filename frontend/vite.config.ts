import path from "path"
import tailwindcss from "@tailwindcss/vite"
import basicSsl from "@vitejs/plugin-basic-ssl"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    tailwindcss(),
    // `npm run dev:phone` uses HTTPS: phones only allow the camera on https://
    mode === "phone" && basicSsl(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // The browser calls /api/seller/me, Vite forwards it to FastAPI as /seller/me.
      // Same origin for the browser, so no CORS needed in development
      "/api": {
        target: "http://localhost:8000",
        rewrite: (url) => url.replace(/^\/api/, ""),
      },
    },
  },
}))
