# Test evidence must match the claim

The founder can explain that analytics failure must not block Threadwise and that a backend test can pass while the Gmail-facing experience fails, because those tests exercise different boundaries. The remaining gap is the distinction between the normal installed-extension path and the live Gmail acceptance harness: the harness automates actions against a real Gmail page, but may use host-driven injection and therefore does not prove normal installed-extension parity by itself.

**Evidence** — Correctly answered the PostHog failure and backend-versus-frontend questions; identified founder click-through as strongest evidence for the exact installed-extension claim; asked for clarification about the live harness.

**Implications** — Next review should retest the four evidence layers and ask the founder to match a specific product claim to the appropriate test environment.
