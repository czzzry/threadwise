const LOCAL_ORIGIN = "http://127.0.0.1:8021";
const HEALTH_PATH = "/api/health";
const HEALTH_SERVICE_ID = "threadwise-gmail-companion";
const HEALTH_TIMEOUT_MS = 5000;
const HARNESS_STATE_TIMEOUT_MS = 30000;

async function fetchJson(path, options = {}) {
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs || 0;
  const timeoutId = timeoutMs > 0 ? setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    const response = await fetch(`${LOCAL_ORIGIN}${path}`, {
      method: options.method || "GET",
      headers: options.headers || { "Content-Type": "application/json" },
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
      timeoutMs: HARNESS_STATE_TIMEOUT_MS,
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

  return false;
});

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id) {
    return;
  }
  await chrome.tabs.sendMessage(tab.id, { type: "email-agent:toggle" }).catch(() => undefined);
});
