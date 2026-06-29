const appUrl = process.argv[2] || "http://127.0.0.1:8765/";
const cdpBase = process.argv[3] || "http://127.0.0.1:9222";

const target = await createTarget(appUrl);
const socket = new WebSocket(target.webSocketDebuggerUrl);
let nextId = 1;
const pending = new Map();

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) {
      reject(new Error(message.error.message));
    } else {
      resolve(message.result);
    }
  }
});

await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

try {
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.navigate", { url: appUrl });
  await waitFor(() => evaluate("document.readyState === 'complete'"));

  const ashbyCardText = `
    Array.from(document.querySelectorAll('.item'))
      .find((item) => item.innerText.includes('Ashby <notifications@ashbyhq.com>'))
      .innerText
  `;
  const initial = await evaluate(ashbyCardText);
  const initialUnlabeled = initial.includes("unlabeled") && initial.includes("Heuristic only");

  await evaluate(`
    const textarea = document.querySelector('#instruction');
    textarea.value = 'anything from recruiters, Ashby, Greenhouse, or Lever should be job-related and kept visible';
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('#save-instruction').click();
  `);
  await waitFor(() => evaluate("document.body.innerText.includes('Saved teach-001')"));
  const afterSave = await evaluate(ashbyCardText);

  await evaluate("document.querySelector('#rerun').click()");
  await waitFor(() => evaluate("document.body.innerText.includes('Classification rerun from saved rules.')"));
  const afterRerun = await evaluate(ashbyCardText);

  const result = {
    initialUnlabeled,
    afterSaveHasWork: afterSave.includes("EA/Work"),
    afterSaveHasRule: afterSave.includes("matched teach-001") && afterSave.includes("ashby"),
    afterRerunHasWork: afterRerun.includes("EA/Work"),
    afterRerunHasRule: afterRerun.includes("matched teach-001"),
    ruleCount: await evaluate("document.querySelectorAll('.rule').length"),
    matchedBadgeCount: await evaluate("document.querySelectorAll('.pill.rule-match').length"),
    status: await evaluate("document.querySelector('#status').innerText"),
    title: await evaluate("document.querySelector('h1').innerText"),
  };

  console.log(JSON.stringify(result, null, 2));
  if (
    !result.initialUnlabeled ||
    !result.afterSaveHasWork ||
    !result.afterSaveHasRule ||
    !result.afterRerunHasWork ||
    !result.afterRerunHasRule
  ) {
    process.exitCode = 1;
  }
} finally {
  socket.close();
}

async function createTarget(url) {
  const response = await fetch(`${cdpBase}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
  if (!response.ok) {
    throw new Error(`Could not create Chrome target: ${response.status}`);
  }
  return response.json();
}

function send(method, params = {}) {
  const id = nextId++;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
  });
}

async function evaluate(expression) {
  const result = await send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || "Evaluation failed");
  }
  return result.result.value;
}

async function waitFor(fn, timeoutMs = 5000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await fn()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("Timed out waiting for browser state.");
}
