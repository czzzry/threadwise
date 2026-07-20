# Analytics is a non-authoritative observer

Threadwise connects PostHog as an observability side channel rather than a dependency in the product's decision path. The extension declares a small set of meaningful events, the local companion applies the authoritative privacy/schema gate, and only safe anonymous event data is sent to PostHog EU. Classification, review state, rules, and Gmail writes continue when analytics is disabled or unavailable. This distinction matters because future architecture decisions should never make analytics the source of truth for product behavior.
