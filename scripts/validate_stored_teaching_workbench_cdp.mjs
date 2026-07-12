const appUrl = process.argv[2] || "http://127.0.0.1:8766/?batch_id=teachable-review-batch";
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

  const ashbyCardExpression = `
    Array.from(document.querySelectorAll('.item'))
      .find((item) => item.innerText.includes('Ashby <notifications@ashbyhq.com>'))
  `;
  const initialAshby = await evaluate(`${ashbyCardExpression}.innerText`);
  const initialUnlabeled = initialAshby.includes("Suggested labels: (none)");

  await evaluate(`
    const card = ${ashbyCardExpression};
    card.querySelector('.teach-example-checkbox').click();
    document.querySelector('#teaching-instruction').value = 'anything from Ashby should be job-related and kept visible';
    document.querySelector('#preview-teaching-rule').click();
  `);
  await waitFor(() => evaluate("document.querySelector('#fetch-status').innerText.includes('Previewed rule')"));
  const previewText = await evaluate("document.querySelector('#teaching-preview').innerText");

  await evaluate("document.querySelector('#save-teaching-rule').click()");
  await waitFor(() => evaluate("document.body.innerText.includes('Matched teach-001')"));
  const afterSaveAshby = await evaluate(`${ashbyCardExpression}.innerText`);

  const result = {
    initialUnlabeled,
    previewShowsMatch: previewText.includes("1 matches in this batch") && previewText.includes("job-related"),
    afterSaveHasWork: afterSaveAshby.includes("Suggested labels: EA/Work"),
    afterSaveShowsMatchedRule: afterSaveAshby.includes("Matched teach-001"),
    title: await evaluate("document.querySelector('h1').innerText"),
    status: await evaluate("document.querySelector('#fetch-status').innerText"),
  };

  console.log(JSON.stringify(result, null, 2));
  if (
    !result.initialUnlabeled ||
    !result.previewShowsMatch ||
    !result.afterSaveHasWork ||
    !result.afterSaveShowsMatchedRule
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
