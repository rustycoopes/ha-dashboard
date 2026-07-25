# TailAdmin-style tile redesign, with a drawn (not photographic) texture and title mark

**Status:** Accepted
**Date:** 2026-07-25

## Context

The user reviewed HA Dashboard's shipped tiles (Slice 4) against a TailAdmin reference screenshot
and asked for three things: (1) TailAdmin's tile language — icon chips, a big bold number, and a
more pronounced card shadow — brought across to the three status tiles; (2) a background image
"that reflects it's Home Assistant"; (3) a title image reflecting smart-home automation.

(1) is a straightforward reskin. (2) and (3) run directly into organize-me's `DESIGN.md`: the
FamilyWall redesign deliberately keeps the entire authenticated shell (every hosted app's own
pages, not just the Host's) free of photography — "task/scan legibility outranks expression once a
visitor is inside the tool." A literal photo behind this one page's tiles would reverse that call
unilaterally, on one hosted app, without revisiting the platform-wide decision.

## Decision

Ship (1) as asked. Resolve the (2)/(3) tension by satisfying the brief's intent — "this page should
read as Home Assistant / smart-home" — without using photography:

- **Background:** a faint connected-nodes mesh (dots + crossing lines), drawn as an inline SVG data
  URI, in the platform's own `cobalt` token at ~7-12% opacity. It reads as "a network of devices"
  rather than a stock kitchen/living-room photo, and stays quiet enough that the tiles remain the
  first thing the eye lands on. Scoped to this page's own content column (`pages/ha_dashboard.html`)
  via an inline `background-image`, not added to the shared `organizeme-chrome` package — this is a
  one-page exception, not a chrome-wide change.
- **Title mark:** a small hand-drawn glyph (roofline + two signal arcs + an amber hub dot) sitting
  beside the "HA Dashboard" heading, built from `cobalt`/`cobalt-tint`/`amber` only — no new palette
  entries, no imported asset.
- Both were shown to the user as a live, toggleable HTML mockup (Current vs. Proposed, texture
  on/off, light/dark) before implementation, specifically to get a second opinion on whether the
  texture earns its place against the existing no-photography rule. Approved as shown.

Other changes carried over from the same review:

- Icon chip per tile (44px, `rounded-xl`), colored by the tile's existing status logic — `sage`
  tint when the tile is all-clear, `cobalt` tint when it has items to review. This is the same
  zero-vs-nonzero distinction the pre-redesign markup already made (`border-sage/30` vs. neutral
  border); the redesign moves it onto an icon chip and a `badge(..., variant="info")` chip instead
  of a border-color-only signal, but doesn't add a new status class or invent a "danger" meaning
  that wasn't there before.
- Bigger number (`text-2xl` → `text-3xl`) with the tile title demoted to a small label above it,
  matching TailAdmin's number-first hierarchy.
- A two-layer soft shadow (`shadow-[0_1px_2px_rgba(20,20,30,.04),0_12px_24px_-12px_rgba(20,20,30,.16)]`,
  lifting further on hover) replacing the earlier heavier-border/near-flat-shadow treatment.
- The page container widened from `max-w-2xl` to `max-w-4xl` so the existing `sm:grid-cols-3` grid
  actually reads as an airy three-up row (TailAdmin's KPI-row proportions) rather than three cramped
  columns.
- A live "Synced HH:MM" pill in the header, delivered via an `hx-swap-oob` block already-present
  `fetched_at` data in `partials/ha_dashboard_tiles.html`, replacing the old plain `<h1>`. Present
  only on the success path; explicitly cleared (not left stale) on every other state, including a
  fragment reload.
- `TileView` gained an explicit `icon: Literal["updates", "repairs", "integrations"]`-shaped field
  (`app/pages/ha_dashboard_tiles.py`) rather than the partial matching on tile title text or loop
  position, so the icon mapping doesn't silently break if a title copy-edit or a reordering of
  `_build_tiles` ever happens.

## Alternatives considered

- **Real photography for the background**, matching the Host's landing/auth pages. Rejected: those
  pages are pre-login marketing surfaces (Persuade mode); HA Dashboard is inside the authenticated
  shell (Operate mode), where `DESIGN.md` already made this call deliberately, not by omission.
- **No background/title treatment at all**, leaning on color/type/shape alone per the existing
  rule. This was presented to the user as the implicit fallback option; they approved the drawn
  mesh/mark version instead after seeing both live.
- **Icon chip colored per category** (e.g., blue for updates, orange for repairs, red for
  integrations — TailAdmin's own approach) instead of per-status. Rejected: `DESIGN.md` restricts
  color to carrying meaning, not decoration; a fixed per-category palette would be exactly the kind
  of decorative color use the FamilyWall redesign moved away from.

## Consequences

- HA Dashboard now has one small, explicitly-scoped exception to "authenticated shell stays
  photography-free" — not a reversal of the rule, since it's a drawn texture, not a photo, and it's
  local to this app's own template rather than the shared `organizeme-chrome` package. If a future
  hosted app wants something similar, treat this ADR as the precedent to reference, not silently
  copy — it should get its own explicit sign-off the same way this one did.
- `TileView.icon` is now part of `_build_tiles`'s contract; any future fourth tile needs an icon
  entry added to the partial's `_icons` map or it fails loudly (`KeyError` from the Jinja map
  lookup) rather than silently rendering blank.
