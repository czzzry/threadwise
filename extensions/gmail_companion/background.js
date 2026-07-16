const LOCAL_ORIGIN = "http://127.0.0.1:8021";
const HEALTH_PATH = "/api/health";
const HEALTH_SERVICE_ID = "threadwise-gmail-companion";
const HEALTH_TIMEOUT_MS = 5000;
const HARNESS_STATE_TIMEOUT_MS = 30000;
// A bounded live Gmail run can take longer than an ordinary state read.
const GMAIL_CHECK_TIMEOUT_MS = 180000;
// Teaching can include bounded Gmail label mutations across matching inbox messages.
const GMAIL_MUTATION_TIMEOUT_MS = 180000;
const ANALYTICS_DISTINCT_ID_KEY = "threadwise_analytics_distinct_id";
const ANONYMOUS_ID_PATTERN = /^tw_anon_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

async function analyticsDistinctId() {
  const stored = await chrome.storage.local.get(ANALYTICS_DISTINCT_ID_KEY);
  const existing = stored[ANALYTICS_DISTINCT_ID_KEY];
  if (typeof existing === "string" && ANONYMOUS_ID_PATTERN.test(existing)) {
    return existing;
  }
  const created = `tw_anon_${crypto.randomUUID()}`;
  await chrome.storage.local.set({ [ANALYTICS_DISTINCT_ID_KEY]: created });
  return created;
}

async function fetchJson(path, options = {}) {
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs || 0;
  const timeoutId = timeoutMs > 0 ? setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    const distinctId = await analyticsDistinctId();
    const response = await fetch(`${LOCAL_ORIGIN}${path}`, {
      method: options.method || "GET",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
        "X-PostHog-Distinct-Id": distinctId,
      },
      body: options.body,
      signal: controller.signal,
    });
    let payload = null;
    try {
      payload = await response.json();
    } catch (_error) {
      payload = null;
    }
    return {
      ok: response.ok,
      status: response.status,
      payload,
    };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      error: String(error),
    };
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
}

async function probeHealth() {
  const result = await fetchJson(HEALTH_PATH, { method: "GET", timeoutMs: HEALTH_TIMEOUT_MS });
  if (!result.ok) {
    return {
      kind: "helper-unreachable",
      label: "Helper unreachable",
      details: result.error || "Could not reach the local companion.",
      health_path: HEALTH_PATH,
    };
  }

  const payload = result.payload || {};
  if (payload.service_id && payload.service_id !== HEALTH_SERVICE_ID) {
    return {
      kind: "wrong-service",
      label: "Wrong service on port",
      details: `Something else is responding on ${LOCAL_ORIGIN}.`,
      service_id: payload.service_id,
      service_name: payload.service_name || "",
      health_path: payload.health_path || HEALTH_PATH,
    };
  }
  if (payload.status && payload.status !== "ready") {
    return {
      kind: "health-failed",
      label: "Health check failed",
      details: `Threadwise reported status=${JSON.stringify(payload.status)}.`,
      service_id: payload.service_id || HEALTH_SERVICE_ID,
      service_name: payload.service_name || "",
      health_path: payload.health_path || HEALTH_PATH,
    };
  }
  return {
    kind: "ready",
    label: "Ready",
    details: `Threadwise is responding at ${LOCAL_ORIGIN}.`,
    service_id: payload.service_id || HEALTH_SERVICE_ID,
    service_name: payload.service_name || "",
    health_path: payload.health_path || HEALTH_PATH,
  };
}

function apiTimeoutMs(path) {
  if (path === "/api/gmail-check-run") {
    return GMAIL_CHECK_TIMEOUT_MS;
  }
  if (path === "/api/teach-apply" || path === "/api/safety-apply") {
    return GMAIL_MUTATION_TIMEOUT_MS;
  }
  return HARNESS_STATE_TIMEOUT_MS;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message) {
    return false;
  }

  if (message.type === "email-agent:get-state") {
    const query = new URLSearchParams(message.context || {});
    fetchJson(`/api/harness-state?${query.toString()}`, { timeoutMs: HARNESS_STATE_TIMEOUT_MS })
      .then(async (response) => {
        if (response.ok) {
          sendResponse({
            ok: true,
            payload: response.payload,
            connection_state: {
              kind: "ready",
              label: "Ready",
              details: "Threadwise is connected.",
            },
          });
          return;
        }
        const connectionState = await probeHealth();
        sendResponse({
          ok: false,
          error: "Could not reach local companion server.",
          connection_state: connectionState,
        });
      })
      .catch(async (error) => {
        const connectionState = await probeHealth();
        sendResponse({
          ok: false,
          error: String(error),
          connection_state: connectionState,
        });
      });

    return true;
  }

  if (message.type === "email-agent:api") {
    fetchJson(message.path, {
      method: message.method || "GET",
      timeoutMs: apiTimeoutMs(message.path),
      body: message.body ? JSON.stringify(message.body) : undefined,
    })
      .then(async (response) => {
        if (response.ok) {
          sendResponse({
            ok: true,
            payload: response.payload,
          });
          return;
        }
        const connectionState = await probeHealth();
        sendResponse({
          ok: false,
          error: String(response.payload?.error || response.error || "Could not reach local companion server."),
          payload: response.payload,
          status: response.status,
          connection_state: connectionState,
        });
      })
      .catch(async (error) => {
        const connectionState = await probeHealth();
        sendResponse({
          ok: false,
          error: String(error),
          connection_state: connectionState,
        });
      });

    return true;
  }

  if (message.type === "threadwise:analytics") {
    fetchJson("/api/analytics/capture", {
      method: "POST",
      timeoutMs: HEALTH_TIMEOUT_MS,
      body: JSON.stringify({
        event: message.event,
        properties: message.properties,
      }),
    })
      .then((response) => sendResponse({ ok: response.ok, payload: response.payload }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }

  return false;
});

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id) {
    return;
  }
  await chrome.tabs.sendMessage(tab.id, { type: "email-agent:toggle" }).catch(() => undefined);
});
