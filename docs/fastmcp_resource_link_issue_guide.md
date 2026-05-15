# FastMCP Proxy ResourceLink Issue Guide

Use this as a copy/rewrite starting point for an upstream FastMCP issue. Keep
the code blocks and concrete examples; rewrite the prose however you want.

## Suggested Title

```text
Namespace transform rewrites listed resource URIs but not ResourceLink URIs returned from proxied tools
```

## Short Summary

```text
When a FastMCP proxy has a Namespace transform, listed resources and resource
templates are correctly namespaced, and namespaced resource reads work.
However, ResourceLink content returned inside a proxied tools/call result keeps
the raw upstream URI instead of the downstream namespaced URI.
```

## Why This Looks Like A Proxy Bug

```text
The proxy is already doing the hard part correctly for normal resource surfaces:

- resources/list returns namespaced URIs
- resource_templates/list returns namespaced URI templates
- resources/read accepts the namespaced URI and reverses it upstream

Only ResourceLink content inside tools/call results escapes with the upstream
URI unchanged. That makes the returned link unusable from the downstream client
even though the same resource is available through the proxy under its
namespaced URI.
```

## Minimal Example

```python
from fastmcp.server import create_proxy
from fastmcp.server.transforms import Namespace

proxy = create_proxy(upstream_client, name="Proxy-everything.default")
proxy.add_transform(Namespace("everything.default"))
```

Given an upstream resource:

```text
demo://resource/dynamic/text/2
```

The proxy correctly exposes it as:

```text
demo://everything.default/resource/dynamic/text/2
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

instead of:

```text
demo://everything.default/resource/dynamic/text/2
```

## Observed Behavior

```text
resources/list:
  upstream: demo://resource/dynamic/text/2
  proxied:  demo://everything.default/resource/dynamic/text/2

resources/read:
  demo://everything.default/resource/dynamic/text/2
  -> works

tools/call result content:
  ResourceLink.uri == demo://resource/dynamic/text/2
  -> raw upstream URI leaks through unchanged
```

## Expected Behavior

```text
If a proxy transform rewrites a resource URI for resources/list and
resources/read, ResourceLink content emitted by proxied tools should expose the
same downstream-facing URI.
```

## Relevant FastMCP Code Paths

`Namespace` already owns the URI mapping:

```python
class Namespace(Transform):
    async def list_resources(...):
        ...

    async def get_resource(...):
        ...
```

`ProxyTool.run(...)` currently returns upstream tool content unchanged:

```python
result = await client.call_tool_mcp(
    name=backend_name,
    arguments=arguments,
    meta=meta,
)

return ToolResult(
    content=result.content,
    structured_content=result.structuredContent,
    meta=result.meta,
)
```

FastMCP's `Transform` base class has hooks for listing/getting tools,
resources, templates, and prompts, but there does not appear to be a hook for
transforming tool results.

## Suggested Direction

```text
Prefer a general result-transform hook over special-casing Namespace logic in
ProxyTool.
```

For example, something in this shape:

```python
class Transform:
    async def tool_result(self, result: ToolResult) -> ToolResult:
        return result
```

Then `Namespace` could rewrite only typed MCP resource-link content:

```python
if isinstance(content, mcp.types.ResourceLink):
    content = content.model_copy(
        update={"uri": self._transform_uri(str(content.uri))}
    )
```

That would keep URI rewriting logic in `Namespace`, where the forward and
reverse resource URI mapping already lives.

## Important Boundary

```text
This is specifically about mcp.types.ResourceLink content inside tools/call
results. Normal resources/list, resource_templates/list, and resources/read
already behave correctly through the proxy.
```

## Extra Note

```text
Session-scoped resources returned by some tools may have additional lifecycle
constraints beyond URI rewriting. This issue is about ordinary ResourceLink URI
projection only.
```
