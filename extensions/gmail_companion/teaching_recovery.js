(() => {
  function text(value) {
    return String(value ?? "").trim();
  }

  function failureDetails(input = {}) {
    const response = input.response && typeof input.response === "object" ? input.response : {};
    const payload = response.payload && typeof response.payload === "object" ? response.payload : {};
    return {
      raw: text(input.error || payload.error || response.error),
      status: Number(response.status || 0),
      connectionKind: text(response.connection_state?.kind).toLowerCase(),
    };
  }

  function action(actionName, label) {
    return [{ action: actionName, label, primary: true }];
  }

  function result(operation, category, title, message, actions, stateLabel = "Nothing changed") {
    return {
      kind: `${operation}-error`,
      category,
      state_label: stateLabel,
      title,
      message,
      actions,
    };
  }

  function describe(input = {}) {
    const operation = input.operation === "apply" ? "apply" : "preview";
    const providerName = text(input.providerName) || "your email";
    const details = failureDetails(input);
    const normalized = details.raw.toLowerCase();
    const previewFailedCopy = "Your instruction was not applied and no labels changed.";
    const applyUnconfirmedCopy = "Threadwise could not confirm whether the change completed. Check the current labels before retrying.";
    const outcomeCopy = operation === "preview" ? previewFailedCopy : applyUnconfirmedCopy;
    const stateLabel = operation === "preview" ? "Nothing changed" : "Status unconfirmed";
    const staleExtension = [
      "extension context invalidated",
      "receiving end does not exist",
      "message port closed before a response was received",
    ].some((phrase) => normalized.includes(phrase));
    if (staleExtension) {
      return result(
        operation,
        "stale-extension",
        `Refresh ${providerName} to continue`,
        operation === "preview"
          ? `Threadwise was updated while this ${providerName} tab was open. ${previewFailedCopy} Refresh ${providerName}, then enter the instruction again.`
          : `Threadwise was updated while this ${providerName} tab was open. ${applyUnconfirmedCopy} Refresh ${providerName}, then check the current labels.`,
        action("reload-provider-tab", `Refresh ${providerName}`),
        stateLabel,
      );
    }

    const companionOffline = details.connectionKind === "helper-unreachable"
      || normalized.includes("failed to fetch")
      || normalized.includes("could not reach");
    if (companionOffline) {
      return result(
        operation,
        "companion-offline",
        "Threadwise is stopped",
        `${outcomeCopy} Start Threadwise from its menu-bar control, then check the connection here.`,
        action("force-refresh", "Check connection"),
        stateLabel,
      );
    }

    if (details.connectionKind === "wrong-service") {
      return result(
        operation,
        "wrong-service",
        "Threadwise cannot use its connection",
        `Another app is using Threadwise's local connection. ${outcomeCopy}`,
        action("force-refresh", "Check connection"),
        stateLabel,
      );
    }

    const aiNotConfigured = normalized.includes("llm review is not configured")
      || normalized.includes("openai key")
      || normalized.includes("api key");
    if (aiNotConfigured) {
      return result(
        operation,
        "ai-not-configured",
        "AI review is not connected",
        `Threadwise could not ask the AI to interpret your instruction. ${outcomeCopy} Open Threadwise Control and reconnect the private OpenAI key.`,
        action("force-refresh", "Check AI connection"),
        stateLabel,
      );
    }

    const aiUnavailable = normalized.includes("llm review was unavailable")
      || normalized.includes("rate limit")
      || normalized.includes("timed out")
      || normalized.includes("timeout")
      || details.status === 429;
    if (aiUnavailable) {
      return result(
        operation,
        "ai-unavailable",
        "AI review could not finish",
        `Threadwise is connected, but the AI review did not finish. ${outcomeCopy}`,
        action(operation === "apply" ? "retry-apply-teach" : "retry-preview-teach", operation === "apply" ? "Check and retry" : "Try AI preview again"),
        stateLabel,
      );
    }

    if (operation === "apply") {
      return result(
        operation,
        "apply-unconfirmed",
        "Could not confirm this change",
        "Threadwise lost the confirmation for this request. Threadwise will check whether anything changed before retrying, so it will not knowingly apply the same lesson twice.",
        action("retry-apply-teach", "Check and retry"),
        stateLabel,
      );
    }

    return result(
      operation,
      "preview-failed",
      "Could not interpret this instruction",
      "Threadwise is connected, but it could not prepare the AI interpretation. Your instruction was not applied and no labels changed.",
      action("retry-preview-teach", "Try AI preview again"),
    );
  }

  const api = Object.freeze({ describe });
  globalThis.ThreadwiseTeachingRecovery = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})();
