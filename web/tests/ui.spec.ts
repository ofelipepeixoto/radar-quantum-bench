import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { createHash, randomUUID } from 'node:crypto';
import { readFile } from 'node:fs/promises';

const jobs = '/api/v1/comparacoes';
type Circuit = 'bell' | 'ghz' | 'bv';
type Job = { id: string; circuit: Circuit; base_seed: number };

async function startPage(page: Page) {
  const catalog = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v1/experimentos');
  await page.goto('/');
  const response = await catalog;
  expect(response.status()).toBe(200);
  expect((await response.json()).map((item: {id: string}) => item.id)).toEqual(['bell', 'ghz', 'bv']);
  await expect(page.locator('#submit-button')).toBeEnabled();
}

async function submit(page: Page, usingKeyboard = false): Promise<Job> {
  const pending = page.waitForResponse(r =>
    r.request().method() === 'POST' && new URL(r.url()).pathname === jobs);
  if (usingKeyboard) {
    await page.keyboard.press('Enter');
  } else {
    await page.locator('#submit-button').click();
  }
  const response = await pending;
  expect(response.status()).toBe(202);
  const job: Job = await response.json();
  await expect(page).toHaveURL(url => url.searchParams.get('comparacao') === job.id);
  return job;
}

async function waitForComplete(page: Page) {
  await expect(page.locator('#job-state')).toHaveText('Concluída', { timeout: 25_000 });
  await expect(page.locator('#download-link')).toBeVisible();
}

async function assertCountsFromApi(page: Page, job: Job) {
  const response = await page.request.get(`${jobs}/${job.id}/metricas`);
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(result.complete).toBe(true);
  expect(result.total_shots).toBe(20_480);
  const ideal: Record<string, number> = result.conditions.ideal.counts;
  const noisy: Record<string, number> = result.conditions.readout_2pct.counts;
  const parseCount = (cell: string) => Number(cell.replaceAll('.', '').trim());
  const rows = page.locator('#counts-body tr');
  await expect(rows).toHaveCount(Object.keys(ideal).length);
  const seen: string[] = [];
  for (const row of await rows.all()) {
    const cells = await row.locator('td, th').allTextContents();
    const word = cells[0]!;
    seen.push(word);
    expect(parseCount(cells[2]!)).toBe(ideal[word]);
    expect(parseCount(cells[4]!)).toBe(noisy[word]);
  }
  expect(seen.sort()).toEqual(Object.keys(ideal).sort());
  await expect(page.locator('#metrics-body tr')).toHaveCount(2);
}

async function assertReportFromApi(page: Page, job: Job) {
  const response = await page.request.get(`${jobs}/${job.id}/relatorio`);
  expect(response.status()).toBe(200);
  const report = await response.json();
  await expect(page.locator('#report-content')).toBeVisible();
  await expect(page.locator('#report-origin')).toHaveText('Resumo local');
  await expect(page.locator('#report-summary')).toContainText(report.resumo.texto);
  await expect(page.locator('#report-observations li')).toHaveCount(report.observacoes.length);
  for (const observation of report.observacoes) {
    await expect(page.locator('#report-observations')).toContainText(observation.texto);
  }
  const jobResponse = await page.request.get(`${jobs}/${job.id}`);
  expect(report.result_sha256).toBe((await jobResponse.json()).result_sha256);
  expect(report.estado).toBe('completo');
  await expect(page.locator('#report-limitations')).toContainText('não comprova vantagem quântica');
  await expect(page.locator('#report-model-button')).toBeHidden();
  const evidence = report.fatos.find((fact: {id: string}) => fact.id === 'readout_2pct.taxa');
  const link = page.locator(`a[aria-label$="Conferir evidência ${evidence.id}"]`).first();
  await link.click();
  await expect(page.locator('#report-evidence')).toHaveAttribute('open', '');
  const factIndex = report.fatos.findIndex((fact: {id: string}) => fact.id === evidence.id);
  const factRow = page.locator(`#report-fact-${factIndex}`);
  await expect(factRow).toContainText(evidence.unidade);
  await expect(factRow).toContainText(evidence.origem);
  return report;
}

async function accessible(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  const violations = result.violations.map(v => ({ rule: v.id, nodes: v.nodes.map(n => n.target) }));
  expect(violations).toEqual([]);
}

async function setCircuitAndSeed(page: Page, circuit: Circuit, seed: number) {
  // The full label is clickable even when the native radio is visually hidden.
  await page.locator('label').filter({ has: page.locator(`input[value="${circuit}"]`) }).click();
  await page.getByText('Opções avançadas', { exact: true }).click();
  await page.locator('#seed').fill(String(seed));
}

test('teclado, medição Bell real, histórico e exportação do mesmo resultado', async ({ page }, info) => {
  const remoteRequests: string[] = [];
  page.on('request', req => {
    const url = new URL(req.url());
    if (url.protocol.startsWith('http') && url.hostname !== '127.0.0.1') remoteRequests.push(url.href);
  });
  await startPage(page);
  await expect(page.getByRole('radio')).toHaveCount(3);
  await page.screenshot({path: info.outputPath('laboratorio-desktop.png'), fullPage: true});
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Ir para o conteúdo' })).toBeFocused();
  await page.keyboard.press('Enter');
  await page.keyboard.press('Tab');
  const bell = page.locator('input[name=circuit][value=bell]');
  await expect(bell).toBeFocused();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('input[name=circuit][value=ghz]')).toBeChecked();
  await page.keyboard.press('ArrowLeft');
  await expect(bell).toBeChecked();
  await page.keyboard.press('Tab');
  await expect(page.locator('#experiment-form details > summary')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('#submit-button')).toBeFocused();
  const job = await submit(page, true);
  expect(job.circuit).toBe('bell');
  await expect(page.locator('#comparison-title')).toBeFocused();
  await waitForComplete(page);
  await assertCountsFromApi(page, job);
  const report = await assertReportFromApi(page, job);
  for (const extension of ['md', 'json']) {
    const downloadStart = page.waitForEvent('download');
    await page.locator(`#report-download-${extension}`).click();
    const reportDownload = await downloadStart;
    const body = await readFile((await reportDownload.path())!, 'utf-8');
    expect(body).toContain(report.result_sha256);
    if (extension === 'json') expect(JSON.parse(body)).toEqual(report);
    else expect(body).toContain(report.resumo.texto);
  }
  await page.screenshot({path: info.outputPath('bell-desktop.png'), fullPage: true});
  await page.reload();
  await waitForComplete(page);
  await expect(page.locator('#report-summary')).toContainText(report.resumo.texto);
  await expect(page.locator('#job-id')).toContainText(job.id);

  await startPage(page);
  const historyAction = page.locator(`#history-body [data-comparison-id="${job.id}"]`);
  await historyAction.click();
  await expect(page).toHaveURL(url => url.searchParams.get('comparacao') === job.id);
  await waitForComplete(page);
  const link = page.locator('#download-link');
  const endpoint = `${jobs}/${job.id}/exportacao`;
  await expect(link).toHaveAttribute('href', endpoint);
  const started = page.waitForEvent('download');
  await link.click();
  const download = await started;
  expect(download.suggestedFilename()).toBe('Radar-Quantum-Bench-BELL.zip');
  const downloaded = await readFile((await download.path())!);
  const source = await page.request.get(endpoint);
  expect(source.status()).toBe(200);
  expect(source.headers()['content-type']).toContain('application/zip');
  expect(downloaded.subarray(0, 4)).toEqual(Buffer.from([0x50, 0x4b, 3, 4]));
  const digest = (b: Buffer) => createHash('sha256').update(b).digest('hex');
  expect(digest(downloaded)).toBe(digest(await source.body()));
  const noticeDownloadStart = page.waitForEvent('download');
  await page.locator('#license-download').click();
  const notices = await noticeDownloadStart;
  expect(notices.suggestedFilename()).toBe('Radar-Quantum-Bench-LICENCAS.zip');
  const noticeSource = await page.request.get('/api/v1/licencas.zip');
  expect(noticeSource.status()).toBe(200);
  expect(digest(await readFile((await notices.path())!))).toBe(digest(await noticeSource.body()));
  expect(remoteRequests).toEqual([]);
});

for (const [circuit, seed] of [['ghz', 19171], ['bv', 19172]] as const) {
  test(`${circuit} selecionado na tela conserva semente, endereço e contagens`, async ({ page }) => {
    await startPage(page);
    await setCircuitAndSeed(page, circuit, seed);
    const job = await submit(page);
    expect(job.circuit).toBe(circuit);
    expect(job.base_seed).toBe(seed);
    await waitForComplete(page);
    await assertCountsFromApi(page, job);
    await assertReportFromApi(page, job);
  });
}

test('falha simulada de leitura do relatório permite reconectar e preserva as contagens', async ({ page }) => {
  let fail = true;
  await page.route('**/api/v1/comparacoes/*/relatorio', async route => {
    if (fail) await route.fulfill({status: 503, json: {detail: 'Falha de leitura simulada'}});
    else await route.continue();
  });
  await startPage(page);
  const job = await submit(page);
  await waitForComplete(page);
  await expect(page.locator('#report-retry')).toBeVisible();
  await assertCountsFromApi(page, job);
  await expect(page.locator('#download-link')).toBeVisible();
  fail = false;
  await page.locator('#report-retry').click();
  await assertReportFromApi(page, job);
});

test('opção de IA simulada exige clique e seu fallback mantém o resumo e o ZIP', async ({ page }) => {
  await page.route('**/api/v1/relator', route => route.fulfill({
    json: {modelo_local: true, modelo: 'modelo-teste:latest'},
  }));
  let modelCalls = 0;
  await page.route('**/api/v1/comparacoes/*/relatorio', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    modelCalls++;
    // Adapter and proposal validation are exercised in Python. This case checks
    // only the browser behavior when the model returns a validated fallback.
    const source = await page.request.get(route.request().url());
    const fallback = await source.json();
    fallback.fallback_reason = 'tempo_esgotado';
    await route.fulfill({json: fallback});
  });
  await startPage(page);
  const job = await submit(page);
  await waitForComplete(page);
  await expect(page.locator('#report-content')).toBeVisible();
  await expect(page.locator('#report-model-button')).toBeEnabled();
  expect(modelCalls).toBe(0);
  const before = await page.request.get(jobs);
  const ids = (await before.json()).map((item: {id: string}) => item.id);
  await page.locator('#report-model-button').click();
  await expect(page.locator('#report-message')).toContainText('O resumo local está disponível');
  expect(modelCalls).toBe(1);
  await expect(page.locator('#report-origin')).toHaveText('Resumo local');
  await assertCountsFromApi(page, job);
  await expect(page.locator('#download-link')).toBeVisible();
  const after = await page.request.get(jobs);
  expect((await after.json()).map((item: {id: string}) => item.id)).toEqual(ids);
});

test('320 pixels, navegação acessível e tabela dentro da área rolável', async ({ page }, info) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await startPage(page);
  const pageOverflows = () => page.evaluate(() =>
    document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(await pageOverflows()).toBe(false);
  await page.screenshot({path: info.outputPath('laboratorio-320.png'), fullPage: true});
  await accessible(page);
  await setCircuitAndSeed(page, 'bv', 19173);
  await submit(page);
  await waitForComplete(page);
  const grid = page.getByRole('region', {name: 'Contagens por resultado'});
  await expect(grid).toBeVisible();
  await grid.focus();
  await expect(grid).toBeFocused();
  expect(await pageOverflows()).toBe(false);
  await page.screenshot({path: info.outputPath('resultado-320.png'), fullPage: true});
  await accessible(page);
});

test('resposta perdida após envio real conserva uma única comparação após recarregar', async ({ page }) => {
  const attempts: {key: string | undefined; body: string | null; id: string}[] = [];
  await page.route(url => url.pathname === jobs, async route => {
    if (route.request().method() !== 'POST') return route.continue();
    const sent = await route.fetch();
    const job: Job = await sent.json();
    expect(sent.status()).toBe(202);
    attempts.push({key: route.request().headers()['idempotency-key'], body: route.request().postData(), id: job.id});
    if (attempts.length === 1) return route.abort('failed');
    return route.fulfill({ response: sent });
  });
  await startPage(page);
  await setCircuitAndSeed(page, 'ghz', 19174);
  await page.locator('#submit-button').click();
  await expect(page.locator('#form-message')).toContainText(/ler a resposta da API/i);
  await page.reload();
  await expect(page.locator('#submit-button')).toHaveText('Confirmar envio anterior');
  await page.locator('#submit-button').click();
  await waitForComplete(page);
  expect(attempts).toHaveLength(2);
  expect(attempts[0]!.key).toBeTruthy();
  expect(attempts[1]).toEqual(attempts[0]);
  const history = await page.request.get(`${jobs}?limit=100`);
  const matching = (await history.json()).filter((job: Job) => job.base_seed === 19174 && job.circuit === 'ghz');
  expect(matching.map((job: Job) => job.id)).toEqual([attempts[0]!.id]);
  await expect(page).toHaveURL(url => url.searchParams.get('comparacao') === attempts[0]!.id);
});

test('uma resposta 429 simulada aparece no formulário sem abrir resultado', async ({ page }) => {
  await page.route(url => url.pathname === jobs, async route => {
    if (route.request().method() !== 'POST') return route.continue();
    return route.fulfill({status: 429, json: {detail: 'A fila atingiu sua capacidade.'}});
  });
  await startPage(page);
  await page.locator('#submit-button').click();
  await expect(page.locator('#form-message')).toContainText(/fila está cheia/i);
  await expect(page.locator('#download-link')).toBeHidden();
  await expect(page).toHaveURL(url => !url.searchParams.has('comparacao'));
});

test('a API recusa requisição de outra origem no mesmo servidor da interface', async ({ request }) => {
  const response = await request.post(jobs, {
    headers: {Origin: 'https://example.invalid', 'Idempotency-Key': randomUUID()},
    data: {circuit: 'bell'},
  });
  expect(response.status()).toBe(403);
  expect((await response.json()).detail).toContain('Origem');
});
