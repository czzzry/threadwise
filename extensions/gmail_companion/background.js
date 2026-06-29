const LOCAL_ORIGIN = "http://127.0.0.1:8021";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message) {
    return false;
  }

  if (message.type === "email-agent:get-state") {
    const query = new URLSearchParams(message.context || {});
    fetch(`${LOCAL_ORIGIN}/api/harness-state?${query.toString()}`)
      .then(async (response) => {
        const payload = await response.json();
        sendResponse({
          ok: response.ok,
          payload,
        });
      })
      .catch((error) => {
        sendResponse({
          ok: false,
          error: String(error),
        });
      });

    return true;
  }

  if (message.type === "email-agent:api") {
    fetch(`${LOCAL_ORIGIN}${message.path}`, {
      method: message.method || "GET",
      headers: { "Content-Type": "application/json" },
      body: message.body ? JSON.stringify(message.body) : undefined,
    })
      .then(async (response) => {
        const payload = await response.json();
        sendResponse({
          ok: response.ok,
          payload,
        });
      })
      .catch((error) => {
        sendResponse({
          ok: false,
          error: String(error),
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
