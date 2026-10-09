import { rmSync } from 'node:fs'
import { resolve } from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, type Plugin } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// Mock mode = no VITE_SUPABASE_URL. In a live build the mock dataset is removed from dist/.
function stripMock(live: boolean): Plugin {
  let outDir = 'dist'
  return {
    name: 'strip-mock-data',
    apply: 'build',
    configResolved(c) {
      outDir = resolve(c.root, c.build.outDir)
    },
    closeBundle() {
      if (live) rmSync(resolve(outDir, 'mock'), { recursive: true, force: true })
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const live = Boolean(env.VITE_SUPABASE_URL)
  return {
    plugins: [
      react(),
      tailwindcss(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['icons/*.png', 'robots.txt'],
        manifest: {
          name: 'Raswal Leads',
          short_name: 'Leads',
          description: 'Daily qualified leads, sending and follow-ups',
          start_url: '/',
          scope: '/',
          display: 'standalone',
          orientation: 'portrait',
          background_color: '#021422',
          theme_color: '#021422',
          icons: [
            { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
            { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          ],
        },
        workbox: {
          navigateFallback: '/index.html',
          navigateFallbackDenylist: [/^\/mock\//],
          globIgnores: ['mock/**'],
          // Supabase data is never cached by the service worker.
          runtimeCaching: [],
        },
      }),
      stripMock(live),
    ],
  }
})
