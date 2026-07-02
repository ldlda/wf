# React Presentation Mode Before Astro

Status: accepted

The defense demo will first become a presentation-oriented mode inside the
existing React workflow console, because the story needs the same live/replay
state, workflow graph, timeline, interrupt form, and RPC evidence that the
console already owns. Astro or another static slide shell remains available
later for appendix pages or route wrapping, but it is not the primary next
surface for the live product demo.

## Considered Options

**Build Astro slides first.**
This would optimize for static slide composition before the interactive product
story is presentable. It risks turning slides into a wrapper around a cluttered
demo instead of making the demo itself understandable.

**Keep the console as an admin panel and make a separate fake presentation app.**
This would look cleaner quickly, but it would weaken the defense claim that the
workflow substrate is inspectable through real product surfaces. The presentation
may use replay data, but it should still be the same console story and not a
detached mock.

**Adopt a heavy component suite.**
A complete component library could improve baseline consistency, but it would
also impose visual defaults and interaction constraints. The demo needs a
distinct staged workflow narrative, not a standard enterprise dashboard skin.

## Consequences

The next UI work should polish and restructure the existing console before
adding a separate slide app. Presentation mode becomes the bridge between the
working product demo and any future formal deck.
