import { defineConfig } from 'astro/config';

export default defineConfig({
  output: 'static',
  outDir: './dist',
  devToolbar: { enabled: false },
  server: { host: '127.0.0.1' },
  vite: {
    server: {
      proxy: {
        '/api/': { target: 'http://127.0.0.1:8000', changeOrigin: false },
      },
    },
  },
});
