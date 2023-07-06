import { defineConfig } from "vite";
import autoprefixer from "autoprefixer";
import basicSsl from '@vitejs/plugin-basic-ssl';
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    basicSsl(),
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
    https: true,
  },
});
