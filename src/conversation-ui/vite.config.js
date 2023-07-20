import { defineConfig } from "vite";
import autoprefixer from "autoprefixer";
import process from 'process';
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config
export default defineConfig({
  clearScreen: false,
  envPrefix: ['VITE_', 'TAURI_'],
  plugins: [
    react(),
  ],
  css: {
    postcss: {
      plugins: [autoprefixer()],
    },
  },
  build: {
    target: process.env.TAURI_PLATFORM == 'windows' ? 'edge114' : process.env.TAURI_PLATFORM == 'macos' ? 'safari16' : 'chrome115',
    minify: !process.env.TAURI_DEBUG ? 'esbuild' : false,
    sourcemap: !!process.env.TAURI_DEBUG,
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
