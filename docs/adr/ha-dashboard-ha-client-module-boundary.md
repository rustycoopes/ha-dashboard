# HA WebSocket client gets its own services module, despite the doc-library "no services/" precedent

**Status:** Proposed
**Date:** 2026-07-23
**Feature:** [`ha-dashboard`](../features/ha-dashboard/TDD.md)

## Context

[`doc-library-service-layer.md`](https://github.com/rustycoopes/organize-me/blob/main/docs/adr/doc-library-service-layer.md) established that this platform's
newest, smallest hosted apps skip `app/services/` entirely when there's no cross-cutting logic to
justify it — doc-library's CRUD lives directly in query functions on its model modules. ha-dashboard
is a similarly small app by page/route count (one dashboard page, one settings tab), which raises
the question of whether it should follow that same precedent, or diverge.

Unlike doc-library, ha-dashboard's core job isn't CRUD against its own database — it's driving a
stateful external protocol exchange (WebSocket connect → auth → three sequenced commands → one
timeout budget → collapse HA-specific failures into two tile-facing outcomes) against a third-party
system it doesn't control. That's real orchestration logic, not a thin wrapper over `db.add()`/
`db.get()`.

## Decision

Give the HA WebSocket client its own dedicated module — `app/services/ha_client/` (`client.py` for
orchestration, `transport.py` for the injectable transport seam, `errors.py` for the two-bucket
`HAAuthError`/`HAConnectionError` taxonomy) — rather than folding it into a model/query function or
a bare route handler. `event-creator`'s existing `app/services/storage/` (also an external-system
gateway, not CRUD) is the closer precedent here, not doc-library's CRUD-only shape.

Credential persistence itself stays thin — a plain query/upsert function in
`app/models/ha_credential.py`, no service wrapper — matching doc-library's convention for the parts
of this app that genuinely are simple CRUD. The service layer is scoped to the one concern that
actually needs it, not applied app-wide.

The WS client exposes a transport-injection seam (an `HATransport` protocol with a
production-`websockets` implementation and a scripted fake for tests) rather than being tested by
patching the `websockets` library directly — this is what lets the PRD's stated test approach
("unit tests against a mocked/fake WebSocket server") actually hold up as a real seam rather than a
patch that breaks on refactor.

## Alternatives considered

- **Follow doc-library exactly: no `services/`, put WS logic in a route handler or a "model"
  module.** Rejected — the WS client's connect/auth/timeout/failure-mapping logic doesn't belong
  in a route handler (untestable in isolation, would bloat the page route past readability) and
  calling it a "model" module misrepresents it — it's not a database access boundary.
- **Generic `app/services/` package covering both the WS client and credential CRUD**, treating
  the whole app as "big enough for a services layer." Rejected — credential persistence is
  genuinely thin (one table, no business rules beyond the singleton-upsert from the companion ADR)
  and doesn't need the indirection; applying the layer app-wide would just be doc-library's
  rejected reasoning inverted, over-structuring the parts that don't need it.
- **Patch `websockets.connect` directly in tests instead of an injectable transport.** Rejected —
  couples every test to the third-party library's exact API shape and makes it easy to end up
  testing the mock instead of the client's own logic; the transport protocol keeps the seam owned
  by this app's code.

## Consequences

- A future contributor skimming `app/` sees `services/` present here but absent in doc-library —
  this ADR is the answer to "why," and should be linked from the TDD so it doesn't read as
  inconsistency.
- Because the boundary is scoped per-concern (not "this app has a services/ package" as a blanket
  rule), adding a second, unrelated integration later would need its own justification, not an
  automatic slot in the same package.
- The transport-injection seam is a small amount of extra structure (a protocol + two
  implementations) that pays for itself specifically because this client has real failure modes
  worth testing (auth rejected, timeout, malformed response) — not warranted for a client with no
  meaningful failure surface.
