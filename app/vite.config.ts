import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      manifest: {
        name: 'Parts Tally', short_name: 'Parts Tally',
        description: 'Local companion for a Parts Tally device',
        theme_color: '#153b32', background_color: '#f5f7f2', display: 'standalone',
        start_url: '/', scope: '/',
        icons: [{ src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' }]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg}'],
        navigateFallback: '/index.html',
        runtimeCaching: []
      }
    })
  ],
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], css: true, exclude: ['e2e/**', 'node_modules/**'] }
});
