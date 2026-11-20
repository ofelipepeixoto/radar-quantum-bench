import { defineConfig } from '@playwright/test';
import { resolve } from 'node:path';

const port = Number(process.env.RQB_E2E_PORT || '8765');
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error('RQB_E2E_PORT deve ser uma porta TCP válida.');
}
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: './tests',
  testMatch: 'ui.spec.ts',
  timeout: 45_000,
  expect: { timeout: 12_000 },
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL,
    browserName: 'chromium',
    acceptDownloads: true,
    locale: 'pt-BR',
    timezoneId: 'America/Sao_Paulo',
    trace: 'retain-on-failure',
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
    },
  },
  webServer: {
    command: 'python3 web/tests/server.py',
    cwd: resolve(import.meta.dirname, '..'),
    url: `${baseURL}/health`,
    timeout: 30_000,
    reuseExistingServer: false,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 8_000 },
  },
});
