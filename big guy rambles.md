# lda rambles

that was surprisingly tuff response from our first user. it made me think about how we handle @node atm.

atm only one way is allowed: path. If you want to inbuilt a value; please use the the graph input.

our first user doesnt understand this. AT ALL.

this calls to several problems.

## dict use, instead of list[InputMap]

why dict, when we can:

```python
class InputMap(BaseModel, Generic[TypeT]):
  key: SupportToValue[TypeT]
  input: Path
```

same thing

```python
class OutputMap(BaseModel, Generic[TypeT]):
  output: Pathexpr
  key (give me a better key name): SupportToValue[TypeT] 
```

look at this support to value, or use another fitting name.
what it does is:

Path("state.foo") -> TypeT
Literal(TypeT) -> TypeT

two modes that we currently need to PATCH IN. we do not PATCH wf_core if there isnt a greater problem.

### default arguments, and literal()

expand on literal, in wf_authoring we can have some Field bs:

```python
@node(
  in_map = [
    InputMap(dont support this either, use g.use()),
  ]
)
def baz(spam: InputT = "literal input", egg: Input2T = Path(do not support this.)):
  ...
```

so that means wf_authoring.node shouldnt do any field augmentation.

```python
g.use(
  baz,
  in_map = [
    now were talking
  ]
)
```

this SHOULD support both path and literal.

## Context, of some sort

langgraph has 3 ways of storage, if you read tests/rewrite

lets copy that over:
```
 According to https://docs.langchain.com/oss/python/concepts/context, there are three types:

 | type | mut | lifetime |
 | --- | --- | --- |
 |static runtime (context) | static | single run |
 |dynamic runtime (state) | mut | single run |
 |dynamic cross-convo (store) | mut | cross-conversation |

 now what the hell is store
## store

 store is used in langgraph-demo for debugging. but it can be used for more things.
 it saves every turn. every graph nodes. I use InMemoryStore, you can use psql store!
 This allows for picking the work up again after a while for example.
 a lot more versatility there.
```

now we 100% has state. we kinda have store if you skim it (trace), but trace is no store. and Context is patched in through state.

this can be done with support for async, because lowk store is going to give us superpowers.

## complaints come when user uses

not a lot from me rn.