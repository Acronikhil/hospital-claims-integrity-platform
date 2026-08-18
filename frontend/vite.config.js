import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Docker Desktop on Windows doesn't reliably forward filesystem change
    // events into the container over a bind mount, so the default watcher
    // silently misses edits. Polling makes hot-reload actually pick them up.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});
