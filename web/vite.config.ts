import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    // Lets DocsArticlePage import the repo-root ouroboros_architecture.mermaid
    // directly (via a `?raw` import) as its single source of truth, rather than a
    // hand-copied string that could silently drift from the file README.md embeds.
    fs: {
      allow: [path.resolve(import.meta.dirname, '..')],
    },
  },
})
