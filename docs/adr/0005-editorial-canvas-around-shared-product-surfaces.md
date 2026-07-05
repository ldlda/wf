# Use An Editorial Canvas Around Shared Product Surfaces

Status: accepted

The defense presentation will keep one warm editorial identity and temporarily
expand real shared console components within a persistent presentation frame.
It will not switch the entire deck into a dark product theme or maintain
presentation-only copies of product UI, because those approaches break
narrative continuity and make the demo less credible.

## Considered Options

**Switch between light slides and a dark application stage.**
This makes product moments visually distinct, but repeated whole-stage theme
changes feel like separate applications and make transitions harder to follow.

**Build presentation-only product replicas.**
This gives complete control over appearance, but creates evidence that is
visually persuasive while no longer being the actual product surface. Fixes and
interaction behavior would also diverge between `/console` and `/present`.

**Keep the current dashboard shell as the presentation.**
This preserves working behavior, but persistent rails, controls, labels, and
card grids compete with the argument and consume the limited `1280x720` frame.

## Consequences

The audience view uses one fixed, scalable `1280x720` Editorial Canvas. Shared
console graphs, receipts, evidence, and approval forms may expand within it;
presentation code owns framing and choreography rather than alternate product
implementations. Locally dark terminal, code, or evidence insets remain valid
when they communicate content type, but the main sequence does not switch its
global theme.
