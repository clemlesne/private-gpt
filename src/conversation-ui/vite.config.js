import { defineConfig } from "vite";
import autoprefixer from "autoprefixer";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config
export default defineConfig({
  clearScreen: false,
  plugins: [
    react(),
  ],
  css: {
    postcss: {
      plugins: [autoprefixer()],
    },
  },
  build: {
    rollupOptions: {
      output: {
        compact: true,
      },
    },
  },
  server: {
    strictPort: true,
  },
});
