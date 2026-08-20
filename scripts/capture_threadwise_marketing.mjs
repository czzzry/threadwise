import { createRequire } from "node:module";
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const python = process.env.PYTHON || "python3";
const port = Number(process.env.THREADWISE_CAPTURE_PORT || 8879);
const origin = `http://127.0.0.1:${port}`;
const hostPath = "/scripts/fixtures/threadwise_marketing_capture_host.html";
const outputDir = path.join(root, "docs", "assets", "marketing", "product");
const extensionDir = path.join(root, "extensions", "gmail_companion");
const modulePaths = [
  "teaching_recovery.js",
  "analytics.js",
  "onboarding.js",
  "queue_navigation.js",
  "context_actions.js",
  "selected_explanation.js",
  "review_progression.js",
  "coverage.js",
];

execFileSync(python, [path.join(root, "scripts", "export_threadwise_marketing_fixture.py")], {
  cwd: root,
  stdio: "inherit",
});
const fixtures = JSON.parse(
  await fs.readFile(path.join(root, "docs", "demo", "marketing-fixture.json"), "utf8"),
);
await fs.mkdir(outputDir, { recursive: true });

const server = spawn(python, ["-m", "http.server", String(port), "--bind", "127.0.0.1", "--directory", root], {
  cwd: root,
  stdio: "ignore",
});

try {
  await waitForServer(`${origin}${hostPath}`);
  const browser = await chromium.launch({
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
  });
  try {
    for (const provider of ["gmail", "protonmail"]) {
      await captureProvider(browser, provider, fixtures[provider], fixtures[`${provider}_next`]);
    }
  } finally {
    await browser.close();
  }
} finally {
  server.kill("SIGTERM");
}

async function captureProvider(browser, provider, fixture, nextFixture) {
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
    deviceScaleFactor: 1,
    colorScheme: "light",
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const providerName = provider === "protonmail" ? "Proton Mail" : "Gmail";
  await page.addInitScript(({ activeProvider, activeProviderName, state }) => {
    let activeState = state;
    const listeners = [];
    const storageData = {
      threadwise_onboarding_state: {
        version: "2026-08-09-v1",
        status: "completed",
        updated_at: "2026-08-20T00:00:00Z",
      },
    };
    const storage = {
      async get(key) {
        if (typeof key === "string") return { [key]: storageData[key] };
        if (Array.isArray(key)) return Object.fromEntries(key.map((name) => [name, storageData[name]]));
        return { ...storageData };
      },
      async set(values) {
        Object.assign(storageData, values);
      },
    };
    globalThis.chrome = {
      storage: { local: storage },
      runtime: {
        lastError: null,
        getURL(resource) {
          return `${location.origin}/extensions/gmail_companion/${resource}`;
        },
        onMessage: {
          addListener(listener) { listeners.push(listener); },
          removeListener(listener) {
            const index = listeners.indexOf(listener);
            if (index >= 0) listeners.splice(index, 1);
          },
        },
        sendMessage(message, callback) {
          const connectionState = {
            kind: "ready",
            label: "Ready",
            details: "Threadwise is connected.",
          };
          let response = { ok: true, payload: {}, connection_state: connectionState };
          if (message?.type === "email-agent:get-state") {
            response = { ok: true, payload: activeState, connection_state: connectionState };
          } else if (message?.type === "email-agent:probe-health") {
            response = { ok: true, connection_state: connectionState };
          } else if (message?.type === "threadwise:analytics") {
            response = { ok: true, payload: { accepted: true } };
          }
          queueMicrotask(() => callback?.(response));
          return true;
        },
      },
    };
    globalThis.ThreadwiseProvider = Object.freeze({
      id: activeProvider,
      name: activeProviderName,
      canRunManualSync: true,
      hasOpenMessage: () => true,
      selectedContext: () => ({
        ...activeState.selected_context,
        page_url: location.href,
        selected_at: "2026-08-20T00:00:00Z",
      }),
      messageUrl: () => "#",
    });
    globalThis.__setThreadwiseFixture = (nextState) => {
      activeState = nextState;
    };
  }, { activeProvider: provider, activeProviderName: providerName, state: fixture });

  await page.goto(`${origin}${hostPath}?provider=${provider}`, { waitUntil: "networkidle" });
  for (const modulePath of modulePaths) {
    await page.addScriptTag({ path: path.join(extensionDir, modulePath) });
  }
  await page.addScriptTag({ path: path.join(extensionDir, "content.js") });
  await page.waitForSelector("#email-agent-companion-root[data-ea-minimized='true']", { timeout: 15000 });
  await settle(page);
  await page.screenshot({ path: path.join(outputDir, `${provider}-minimized.png`) });

  await page.click("#ea-brand-toggle");
  await page.waitForSelector("[data-ea-selected-state='review']", { timeout: 15000 });
  await settle(page);
  await page.screenshot({ path: path.join(outputDir, `${provider}-review.png`) });
  await page.locator("#email-agent-companion-root").screenshot({
    path: path.join(outputDir, `${provider}-review-detail.png`),
  });

  await page.evaluate((nextState) => {
    document.querySelectorAll("[data-message-id]").forEach((row) => {
      row.classList.toggle("selected", row.getAttribute("data-message-id") === "demo-002");
    });
    document.querySelector("[data-open-sender]").textContent = "CloudLedger <billing@cloudledger.example>";
    document.querySelector("[data-open-subject]").textContent = "Monthly invoice available";
    globalThis.__setThreadwiseFixture(nextState);
    globalThis.__eaTestHooks.forceRefresh();
  }, nextFixture);
  await page.waitForFunction(() => {
    const snapshot = globalThis.__eaTestHooks.getSnapshot();
    return snapshot.selectedEmail?.subject === "Monthly invoice available";
  }, { timeout: 15000 });
  await settle(page);
  const transition = await page.evaluate(() => ({
    hostSubject: document.querySelector("[data-open-subject]")?.textContent?.trim(),
    panelSubject: globalThis.__eaTestHooks.getSnapshot().selectedEmail?.subject || "",
  }));
  if (transition.hostSubject !== transition.panelSubject) {
    throw new Error(`Synthetic next-email capture is inconsistent: ${JSON.stringify(transition)}`);
  }
  await page.screenshot({ path: path.join(outputDir, `${provider}-next.png`) });
  await page.locator("#email-agent-companion-root").screenshot({
    path: path.join(outputDir, `${provider}-next-detail.png`),
  });
  await context.close();
}

async function settle(page) {
  await page.evaluate(() => document.fonts?.ready);
  await page.waitForTimeout(180);
}

async function waitForServer(url) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch (_error) {
      // The server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Timed out waiting for ${url}`);
}
