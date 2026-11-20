type Circuit = "bell" | "ghz" | "bv";
type Condition = "ideal" | "readout_2pct";
type Status = "queued" | "running" | "completed" | "failed";
interface Specification {
  id: Circuit; label: string; base_seed: number; shots: number; repetitions: number;
  qubits: number; measured: number; words: string[]; ideal: Record<string, number>;
}
interface Measurement {
  counts: Record<string, number>; total_shots: number; valid_shots: number;
  valid_fraction: number | null; wilson95: [number, number] | null;
  tvd: number | null; median_ms: number | null; completed_repetitions: number;
}
interface Summary { complete: boolean; conditions: Record<Condition, Measurement> }
interface Job {
  id: string; circuit: Circuit; base_seed: number; status: Status; created_at: string;
  progress?: Summary | null; attempts: {error_code: string | null}[];
}
type Pending =
  | {kind: "create"; key: string; circuit: Circuit; seed: number | null}
  | {kind: "retry"; key: string; id: string};

const api = "/api/v1";
const statuses: Record<Status, string> = {
  queued: "Na fila", running: "Em execução", completed: "Concluída", failed: "Falhou",
};
const conditions = {ideal: "Ideal", readout_2pct: "Ruído de leitura de 2%"} as const;
const modes: Condition[] = ["ideal", "readout_2pct"];
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const num = new Intl.NumberFormat("pt-BR", {maximumFractionDigits: 6});
const pct = new Intl.NumberFormat("pt-BR", {style: "percent", maximumFractionDigits: 4});
const date = new Intl.DateTimeFormat("pt-BR", {dateStyle: "short", timeStyle: "short"});
const absent = "Sem medição";
const percent = (value: number | null) => value == null ? absent : pct.format(value);
function byId<T extends HTMLElement = HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Elemento ausente: ${id}`);
  return element as T;
}
function make<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
}
function row(cells: string[]): HTMLTableRowElement {
  const tr = make("tr");
  for (const cell of cells) tr.append(make("td", cell));
  return tr;
}

class HttpError extends Error {
  constructor(readonly code: number) {
    super(({
      403: "A API recusou a origem desta página. Abra a bancada pelo endereço local.",
      404: "Esta comparação não foi encontrada. Confira o histórico ou o endereço.",
      409: "A operação não é compatível com o estado ou a configuração da comparação.",
      422: "A API recusou os parâmetros. Confira o circuito e a semente.",
      429: "A fila está cheia. Tente novamente quando uma comparação terminar.",
    } as Record<number, string>)[code] ?? `A API devolveu o erro ${code}. Tente novamente.`);
  }
}
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(api + path, {cache: "no-store", ...options});
  if (!res.ok || (options.method === "POST" && res.status !== 202)) throw new HttpError(res.status);
  return await res.json() as T;
}
function explain(err: unknown): string {
  return err instanceof HttpError ? err.message : "Não foi possível ler a resposta da API local. Verifique a conexão e tente novamente.";
}

const form = byId<HTMLFormElement>("experiment-form");
const seedInput = byId<HTMLInputElement>("seed");
const submit = byId<HTMLButtonElement>("submit-button");
const submitText = submit.firstChild;
const submitLabel = submitText?.textContent ?? "Iniciar comparação";
const retry = byId<HTMLButtonElement>("retry-button");
const repeat = byId<HTMLButtonElement>("repeat-button");
const newSeed = byId<HTMLButtonElement>("new-seed-button");
const download = byId<HTMLAnchorElement>("download-link");
const reconnect = byId<HTMLButtonElement>("network-retry");
const formMessage = byId("form-message");
const detailMessage = byId("comparison-message");
const panel = byId("comparison");
const results = byId("result-panel");
const historyBody = byId<HTMLTableSectionElement>("history-body");
const previousPage = byId<HTMLButtonElement>("history-previous");
const nextPage = byId<HTMLButtonElement>("history-next");
const pageSize = 20;
const catalog = new Map<Circuit, Specification>();
const problems = new Map<string, string>();
let connected = false;

function paintConnection() {
  const indicator = byId("connection-status");
  const down = problems.size > 0;
  indicator.dataset.status = down ? "offline" : connected ? "online" : "loading";
  const label = down ? "Requer atenção" : connected ? "API conectada" : "Conectando";
  if (indicator.textContent !== label) indicator.textContent = label;
  reconnect.hidden = !["catalog", "detail", "history"].some(channel => problems.has(channel));
}
function connection(channel: string, error?: unknown) {
  if (error === undefined) { problems.delete(channel); connected = true; }
  else problems.set(channel, explain(error));
  paintConnection();
}

function isCircuit(id: unknown): id is Circuit { return id === "bell" || id === "ghz" || id === "bv"; }
function validSeed(seed: unknown): seed is number {
  return typeof seed === "number" && Number.isInteger(seed) && seed >= 0 && seed <= 4294967295;
}
const storageKey = "rqb.pending";
function readPending(): Pending | null {
  try {
    const raw = sessionStorage.getItem(storageKey);
    if (raw === null) return null;
    const p = JSON.parse(raw);
    if (typeof p?.key !== "string" || !uuidPattern.test(p.key)) return null;
    if (p.kind === "retry" && typeof p.id === "string" && uuidPattern.test(p.id)) return p;
    if (p.kind === "create" && isCircuit(p.circuit) && (p.seed === null || validSeed(p.seed))) return p;
  } catch { /* This tab can still submit safely in memory if storage is unavailable. */ }
  return null;
}
let pending = readPending();
let pendingStored = true;
let sending = false;
let loadingCatalog = false;
let selected: string | null = null;
let current: Job | null = null;
let viewEpoch = 0;
let lastDetail: AbortController | null = null;
let timer: number | undefined;
let historyRequest: AbortController | null = null;
let offset = 0;

function setPending(value: Pending | null) {
  pending = value;
  try {
    if (value) sessionStorage.setItem(storageKey, JSON.stringify(value));
    else sessionStorage.removeItem(storageKey);
    pendingStored = true;
  } catch { pendingStored = false; }
}
function showPendingInputs(action: Pending) {
  if (action.kind !== "create") return;
  const radio = form.querySelector<HTMLInputElement>(`input[name=circuit][value="${action.circuit}"]`);
  if (radio) radio.checked = true;
  seedInput.value = action.seed === null ? "" : String(action.seed);
}
function selectedCircuit(): Circuit | null {
  const value = form.querySelector<HTMLInputElement>('input[name=circuit]:checked')?.value;
  return isCircuit(value) ? value : null;
}
function configure() {
  const circuit = selectedCircuit();
  const spec = circuit && catalog.get(circuit);
  if (spec) {
    seedInput.placeholder = String(spec.base_seed);
    const support = spec.words.filter(word => spec.ideal[word]! > 0);
    const predicted = support.map(word => `${word} (${percent(spec.ideal[word]!)})`).join(" e ");
    const description = `Na distribuição ideal, os resultados esperados são ${predicted}. O circuito mede ${spec.measured} de ${spec.qubits} qubits.`;
    const target = byId("experiment-description");
    if (target.textContent !== description) target.textContent = description;
  }
  const locked = sending || pending !== null;
  for (const input of form.querySelectorAll<HTMLInputElement>('input[name=circuit]')) input.disabled = locked;
  seedInput.disabled = locked;
  submit.disabled = sending || !(pending || spec);
  const label = sending ? "Enviando…" : pending ? "Confirmar envio anterior" : submitLabel;
  if (submitText && submitText.textContent !== label) submitText.textContent = label;
  retry.disabled = sending || (pending !== null && (pending.kind !== "retry" || pending.id !== selected));
  repeat.disabled = newSeed.disabled = locked;
}
async function loadCatalog() {
  if (loadingCatalog) return;
  loadingCatalog = true;
  try {
    const data = await request<Specification[]>("/experimentos");
    if (!data.length) throw new Error("Catálogo vazio");
    catalog.clear();
    for (const spec of data) catalog.set(spec.id, spec);
    connection("catalog");
    if (!pending && !sending && !problems.has("post")) formMessage.textContent = "";
    if (current) paint(current);
  } catch (err) {
    connection("catalog", err);
    formMessage.textContent = `Catálogo indisponível. ${explain(err)}`;
  } finally { loadingCatalog = false; configure(); }
}

function historyStatus(job: Job) {
  const status = historyBody.querySelector<HTMLElement>(`[data-job-state="${job.id}"]`);
  if (status) { status.textContent = statuses[job.status]; status.dataset.status = job.status; }
}
function markSelected() {
  for (const button of historyBody.querySelectorAll<HTMLButtonElement>("button[data-comparison-id]")) {
    if (button.dataset.comparisonId === selected) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
  }
}
async function loadHistory(target = offset) {
  historyRequest?.abort();
  const controller = new AbortController();
  historyRequest = controller;
  try {
    const jobs = await request<Job[]>(`/comparacoes?limit=${pageSize}&offset=${target}`, {signal: controller.signal});
    if (historyRequest !== controller) return;
    connection("history");
    offset = target;
    const frag = document.createDocumentFragment();
    for (const job of jobs) {
      const line = make("tr");
      const name = catalog.get(job.circuit)?.label ?? job.circuit.toUpperCase();
      const state = make("span", statuses[job.status]);
      state.dataset.jobState = job.id;
      state.dataset.status = job.status;
      const stateCell = make("td"); stateCell.append(state);
      const action = make("button", "Abrir");
      action.type = "button"; action.dataset.comparisonId = job.id;
      action.setAttribute("aria-label", `Abrir comparação ${name}, semente ${job.base_seed}`);
      const actionCell = make("td"); actionCell.append(action);
      line.append(make("td", name), stateCell, make("td", date.format(new Date(job.created_at))), actionCell);
      frag.append(line);
    }
    // A manual refresh can also be triggered from a focused history row.
    const activeId = document.activeElement instanceof HTMLElement ? document.activeElement.dataset.comparisonId : undefined;
    historyBody.replaceChildren(frag);
    if (current) historyStatus(current);
    markSelected();
    if (activeId && uuidPattern.test(activeId))
      historyBody.querySelector<HTMLButtonElement>(`[data-comparison-id="${activeId}"]`)?.focus({preventScroll: true});
    const empty = byId("history-empty");
    empty.hidden = jobs.length > 0;
    empty.textContent = target ? "Não há mais comparações nesta página." : "Nenhuma comparação registrada.";
    previousPage.disabled = target === 0;
    nextPage.disabled = jobs.length < pageSize;
    byId("history-page").textContent = `Página ${Math.floor(target / pageSize) + 1}`;
  } catch (err) {
    if (controller.signal.aborted) return;
    connection("history", err);
    const help = byId("history-empty"); help.hidden = false;
    help.textContent = `Histórico indisponível. ${explain(err)}`;
  }
}

function distribution(spec: Specification, summary: Summary) {
  const countRows = document.createDocumentFragment();
  const bars = document.createDocumentFragment();
  for (const word of spec.words) {
    const theoretical = spec.ideal[word] ?? null;
    const values = modes.map(mode => {
      const data = summary.conditions[mode];
      const count = data.counts[word] ?? null;
      const fraction = count !== null && data.total_shots > 0 ? count / data.total_shots : null;
      return {count, fraction};
    });
    const cells = [word, percent(theoretical)];
    for (const {count, fraction} of values) cells.push(count === null ? absent : num.format(count), percent(fraction));
    countRows.append(row(cells));
    const group = make("div"); group.className = "chart-group";
    const label = make("span", word); label.className = "chart-word"; group.append(label);
    const probabilities = [theoretical, ...values.map(v => v.fraction)];
    for (const [index, series] of ["theory", "ideal", "noisy"].entries()) {
      const track = make("div"); track.className = "chart-track"; track.dataset.series = series;
      const bar = make("span"); bar.className = "chart-bar"; bar.dataset.series = series;
      const value = probabilities[index];
      if (value != null) bar.style.width = `${100 * value}%`;
      track.append(bar); group.append(track);
    }
    bars.append(group);
  }
  byId("distribution-chart").replaceChildren(bars);
  byId("counts-body").replaceChildren(countRows);
}
function paint(job: Job) {
  const spec = catalog.get(job.circuit);
  const progress = job.progress;
  const complete = job.status === "completed" && progress?.complete === true;
  byId("comparison-title").textContent = `Comparação ${spec?.label ?? job.circuit.toUpperCase()}`;
  byId("job-id").textContent = job.id;
  const seed = document.getElementById("job-seed");
  if (seed) seed.textContent = ` · Semente ${job.base_seed}`;
  const state = byId("job-state"); state.dataset.status = job.status;
  if (state.textContent !== statuses[job.status]) state.textContent = statuses[job.status];
  const messages = {
    queued: "Aguardando o executor local.",
    running: "O executor está registrando as medições.",
    completed: complete ? "Medições concluídas nas duas condições." : "O resultado completo ainda não está disponível.",
    failed: "A execução falhou. Você pode retomar a mesma comparação.",
  };
  if (detailMessage.textContent !== messages[job.status]) detailMessage.textContent = messages[job.status];
  const progressNodes = modes.map(mode => {
    const box = make("div"); box.className = "condition";
    const completed = progress?.conditions[mode]?.completed_repetitions;
    const detail = completed == null ? "Aguardando medições" :
      `${completed}/${spec?.repetitions ?? "?"} repetições`;
    box.append(make("strong", conditions[mode]), make("span", detail)); return box;
  });
  byId("conditions").replaceChildren(...progressNodes);
  results.hidden = !(complete && spec);
  if (complete && spec && progress) {
    const rows = modes.map(mode => {
      const data = progress.conditions[mode];
      const interval = data.wilson95?.map(percent).join(" a ") ?? absent;
      return row([conditions[mode], `${percent(data.valid_fraction)} (${num.format(data.valid_shots)}/${num.format(data.total_shots)})`,
        interval, data.tvd == null ? absent : num.format(data.tvd),
        data.median_ms == null ? absent : `${num.format(data.median_ms)} ms`]);
    });
    byId("metrics-body").replaceChildren(...rows);
    distribution(spec, progress);
  }
  retry.hidden = job.status !== "failed";
  repeat.hidden = newSeed.hidden = !complete;
  download.hidden = !complete;
  if (complete) {
    download.href = `${api}/comparacoes/${job.id}/exportacao`;
    download.download = `Radar-Quantum-Bench-${job.circuit.toUpperCase()}.zip`;
  } else download.removeAttribute("href");
  historyStatus(job); configure();
}

function cancelDetail() {
  window.clearTimeout(timer); timer = undefined;
  lastDetail?.abort(); lastDetail = null;
}
async function refreshDetail() {
  if (!selected) return;
  cancelDetail();
  const id = selected;
  const controller = new AbortController(); lastDetail = controller;
  try {
    const job = await request<Job>(`/comparacoes/${id}`, {signal: controller.signal});
    if (controller.signal.aborted || selected !== id || job.id !== id) return;
    connection("detail"); current = job; paint(job);
    if (job.status === "queued" || job.status === "running") {
      timer = window.setTimeout(() => { void refreshDetail(); }, 600);
    }
  } catch (err) {
    if (controller.signal.aborted || selected !== id) return;
    connection("detail", err); current = null; detailMessage.textContent = explain(err);
    // A stale completion must never leave a download active on an unverified response.
    download.hidden = true; download.removeAttribute("href");
    retry.hidden = repeat.hidden = newSeed.hidden = true;
    results.hidden = true;
  } finally { if (lastDetail === controller) lastDetail = null; }
}
function openJob(id: string | null, push = false, focus = false) {
  viewEpoch++; cancelDetail();
  selected = id; current = null;
  problems.delete("detail");
  paintConnection();
  if (push) {
    const url = new URL(location.href);
    if (id) url.searchParams.set("comparacao", id); else url.searchParams.delete("comparacao");
    if (url.href !== location.href) history.pushState(null, "", url);
  }
  panel.hidden = id === null;
  results.hidden = retry.hidden = repeat.hidden = newSeed.hidden = download.hidden = true;
  download.removeAttribute("href"); byId("conditions").replaceChildren();
  markSelected();
  if (id === null) return;
  byId("job-id").textContent = id; byId("job-state").textContent = "";
  const seed = document.getElementById("job-seed"); if (seed) seed.textContent = "";
  const title = byId("comparison-title"); title.textContent = "Comparação";
  if (focus) title.focus();
  if (!uuidPattern.test(id)) {
    detailMessage.textContent = "O endereço contém um identificador inválido. Escolha uma comparação no histórico.";
    return;
  }
  detailMessage.textContent = "Consultando comparação…";
  void refreshDetail();
}
async function send(action: Pending) {
  if (sending) return;
  const originEpoch = viewEpoch;
  setPending(action); showPendingInputs(action); sending = true; configure();
  formMessage.textContent = action.kind === "retry" ? "Solicitando nova tentativa…" : "Enviando comparação…";
  try {
    const path = action.kind === "create" ? "/comparacoes" : `/comparacoes/${action.id}/retentativas`;
    const headers: Record<string,string> = {"Idempotency-Key": action.key};
    let body: string | undefined;
    if (action.kind === "create") {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify({circuit: action.circuit, base_seed: action.seed});
    }
    const job = await request<Job>(path, {method: "POST", headers, body});
    if (!uuidPattern.test(job.id)) throw new Error("Resposta da fila inválida");
    connection("post"); setPending(null);
    formMessage.textContent = "A fila confirmou o recebimento da comparação.";
    const stillHere = originEpoch === viewEpoch;
    if (stillHere) openJob(job.id, true, true);
    void loadHistory(stillHere ? 0 : offset);
  } catch (err) {
    if (err instanceof HttpError && [403, 404, 409, 422, 429].includes(err.code)) {
      // These API rejections do not enqueue work. The next user action may change the inputs.
      setPending(null); connection("post");
      formMessage.textContent = explain(err);
      if (action.kind === "retry" && selected === action.id) void refreshDetail();
    } else {
      connection("post", err);
      const storageNote = pendingStored ? "" : " Mantenha esta aba aberta para preservar o pedido.";
      formMessage.textContent = `${explain(err)} Use “Confirmar envio anterior” para consultar o mesmo pedido.${storageNote}`;
    }
  } finally { sending = false; configure(); }
}
form.addEventListener("change", configure);
form.addEventListener("submit", e => {
  e.preventDefault();
  if (sending) return;
  if (pending) { void send(pending); return; }
  const circuit = selectedCircuit();
  if (!circuit || !catalog.has(circuit)) return;
  const raw = seedInput.value.trim();
  const seed = raw === "" ? null : Number(raw);
  if (seed !== null && (!/^\d+$/.test(raw) || !validSeed(seed))) {
    formMessage.textContent = "Use um número inteiro de 0 a 4294967295 para a semente.";
    seedInput.focus(); return;
  }
  void send({kind: "create", key: crypto.randomUUID(), circuit, seed});
});
retry.addEventListener("click", () => {
  if (!current || sending || current.status !== "failed") return;
  if (pending && (pending.kind !== "retry" || pending.id !== current.id)) return;
  void send(pending ?? {kind: "retry", key: crypto.randomUUID(), id: current.id});
});
function repeatComparison(changeSeed: boolean) {
  if (!current || pending || sending || current.status !== "completed" || !current.progress?.complete) return;
  let seed = current.base_seed;
  if (changeSeed) {
    do { seed = crypto.getRandomValues(new Uint32Array(1))[0]!; } while (seed === current.base_seed);
  }
  void send({kind: "create", key: crypto.randomUUID(), circuit: current.circuit, seed});
}
repeat.addEventListener("click", () => repeatComparison(false));
newSeed.addEventListener("click", () => repeatComparison(true));
historyBody.addEventListener("click", event => {
  const target = event.target instanceof Element ? event.target.closest<HTMLButtonElement>("button[data-comparison-id]") : null;
  if (target?.dataset.comparisonId) openJob(target.dataset.comparisonId, true, true);
});
byId("refresh-history").addEventListener("click", () => { void loadHistory(); });
previousPage.addEventListener("click", () => { void loadHistory(Math.max(0, offset - pageSize)); });
nextPage.addEventListener("click", () => { void loadHistory(offset + pageSize); });
reconnect.addEventListener("click", () => {
  if (problems.has("catalog")) void loadCatalog();
  if (problems.has("history")) void loadHistory();
  if (problems.has("detail") && selected && uuidPattern.test(selected)) void refreshDetail();
});
window.addEventListener("popstate", () => {
  const next = new URL(location.href).searchParams.get("comparacao");
  if (next !== selected) openJob(next);
});
if (pending) {
  showPendingInputs(pending);
  formMessage.textContent = "Um envio anterior aguarda confirmação. Tente novamente para consultar o mesmo pedido.";
  connection("post", new Error("Pending"));
}
configure();
void loadCatalog();
void loadHistory();
openJob(new URL(location.href).searchParams.get("comparacao"));
