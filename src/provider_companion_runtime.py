from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class CompanionSurface(Protocol):
    snapshot_before_write: bool

    def sidebar(self, selected_context: dict | None) -> dict: ...

    def harness(self, selected_context: dict | None) -> dict: ...

    def start_write(self, work: Callable[[], dict]) -> None: ...

    def retry_write(self) -> dict: ...

    def after_apply(self, selected_context: dict) -> None: ...

    def after_write(self) -> None: ...


class GmailCompanionSurface:
    """Map the Gmail state service onto the shared provider lifecycle."""

    snapshot_before_write = False

    def __init__(self, runtime_state: object) -> None:
        self._runtime_state = runtime_state

    def sidebar(self, selected_context: dict | None) -> dict:
        return self._runtime_state.sidebar(selected_context)

    def harness(self, selected_context: dict | None) -> dict:
        return self._runtime_state.harness(selected_context)

    def start_write(self, work: Callable[[], dict]) -> None:
        self._runtime_state.start_teaching_write(work)

    def retry_write(self) -> dict:
        return self._runtime_state.retry_teaching_writes()

    def after_apply(self, selected_context: dict) -> None:
        self._runtime_state.start_teaching_refresh(selected_context)

    def after_write(self) -> None:
        self._runtime_state.invalidate()


class ProtonCompanionSurface:
    """Map the lazy Proton console onto the shared provider lifecycle."""

    snapshot_before_write = True

    def __init__(self, console_loader: Callable[[], object]) -> None:
        self._console_loader = console_loader

    def sidebar(self, selected_context: dict | None) -> dict:
        return self.harness(selected_context)["sidebar_state"]

    def harness(self, selected_context: dict | None) -> dict:
        return self._console_loader().companion_harness(selected_context)

    def start_write(self, work: Callable[[], dict]) -> None:
        self._console_loader().start_companion_write(work)

    def retry_write(self) -> dict:
        return self._console_loader().retry_companion_write()

    def after_apply(self, selected_context: dict) -> None:
        return None

    def after_write(self) -> None:
        return None


class ProviderCompanionRuntime:
    """Own one provider's teaching workflow and companion lifecycle."""

    def __init__(
        self,
        *,
        provider: str,
        workflow: object,
        teaching_adapter: object,
        surface: CompanionSurface,
    ) -> None:
        self.provider = provider
        self.workflow = workflow
        self._teaching_adapter = teaching_adapter
        self._surface = surface

    def sidebar(self, selected_context: dict | None) -> dict:
        return self._surface.sidebar(selected_context)

    def harness(self, selected_context: dict | None) -> dict:
        return self._surface.harness(selected_context)

    def build_preview(self, payload: dict, *, include_existing_impact: bool = True) -> dict:
        return self.workflow.build_preview(
            payload,
            include_existing_impact=include_existing_impact,
        )

    def finish_preview_impact(self, preview: dict) -> dict:
        return self.workflow.finish_preview_impact(preview)

    def preview_backfill(self, preview: dict) -> dict:
        return self._teaching_adapter.preview_backfill(preview)

    def exclude_match(self, payload: dict) -> dict:
        return self.workflow.exclude_match(payload)

    def decide_amendment(self, payload: dict) -> dict:
        return self.workflow.decide_amendment(payload)

    def apply(self, payload: dict, *, defer_provider_write: bool = False):
        return self.workflow.apply(
            payload,
            defer_provider_write=defer_provider_write,
        )

    def complete_deferred_write(self, request) -> dict:
        return self.workflow.complete_deferred_write(request)

    def submit_deferred_write(
        self,
        work: Callable[[], dict],
        selected_context: dict,
    ) -> dict | None:
        snapshot = (
            self.sidebar(selected_context)
            if self._surface.snapshot_before_write
            else None
        )
        self._surface.start_write(work)
        return snapshot

    def retry_write(self) -> dict:
        return self._surface.retry_write()

    def after_apply(self, selected_context: dict) -> None:
        self._surface.after_apply(selected_context)

    def after_write(self) -> None:
        self._surface.after_write()


class CompanionProviderRuntimes:
    """Resolve the provider runtime once for every shared companion operation."""

    def __init__(
        self,
        runtimes: list[ProviderCompanionRuntime],
        *,
        default_provider: str = "gmail",
    ) -> None:
        self._runtimes = {runtime.provider: runtime for runtime in runtimes}
        if default_provider not in self._runtimes:
            raise ValueError("The default provider must have a registered runtime.")
        self._default_provider = default_provider

    def for_provider(self, provider: str) -> ProviderCompanionRuntime:
        return self._runtimes.get(provider, self._runtimes[self._default_provider])

    def for_payload(self, payload: dict) -> ProviderCompanionRuntime:
        selected_context = payload.get("selected_context") or {}
        preview = payload.get("preview") or {}
        proposal = preview.get("proposal") or {}
        provider = str(
            selected_context.get("provider")
            or proposal.get("provider")
            or preview.get("provider")
            or "gmail"
        )
        return self.for_provider(provider)
