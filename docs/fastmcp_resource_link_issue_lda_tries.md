---
title: Namespace transform does not rewrite ResourceLink URIs returned from proxied tools
---

## summary

With a `Namespace` transform on a proxy, listed resources are namespaced
correctly.
However, `ResourceLink.uri` values returned from a proxied
`tools/call` result keep the upstream URI instead of the proxied URI.

Tested on FastMCP `3.3.0`.

## minimal example

```python
from fastmcp.server import create_proxy
from fastmcp.server.transforms import Namespace

proxy = create_proxy(upstream_client, name="Proxy-everything")
proxy.add_transform(Namespace("everything"))
```

An upstream resource looking like this:

```text
demo://resource/dynamic/text/2
```

will be exposed correctly as:

```text
demo://everything/resource/dynamic/text/2
```

But if an upstream tool returns:

```python
mcp.types.ResourceLink(
    type="resource_link",
    name="dynamic-text",
    uri="demo://resource/dynamic/text/2",
)
```

the proxied tool result still contains:

```text
demo://resource/dynamic/text/2
```

## Observed Behavior

```text
resources/list:
  upstream: demo://resource/dynamic/text/2
  proxied:  demo://everything/resource/dynamic/text/2

resources/read:
  demo://everything/resource/dynamic/text/2
  -> works

tools/call result content:
  ResourceLink.uri == demo://resource/dynamic/text/2
  -> raw upstream URI leaks through unchanged
```

## expected behavior

`ResourceLink` content returned by proxied tools should expose the same proxied
URI as `resources/list` and `resources/read`.

## scope of this issue

This is specifically about `mcp.types.ResourceLink` content inside `tools/call`
results. Normal `resources/list`, `resource_templates/list`, and
`resources/read` already behave correctly through the proxy.

Session-scoped resources returned by some tools may have additional lifecycle
constraints beyond URI rewriting. This issue is about ordinary ResourceLink URI
projection only.
