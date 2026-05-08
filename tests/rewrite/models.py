from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

from wf_authoring.schemas import state_field


class SophisticatedRates(TypedDict):
    r_1: float
    r_10: float
    r_80: float  # 0.5 sometimes, 1
    # not including 240 because ill force it by simple_counter, the pool split probably forces half, dealing w ts is ahh.
    r_240: float  # i caved


# i copy things over, not the greatest design but im not doing deep fixes.


class SophisticatedCounter(TypedDict):
    c_10: int  # how do i convey "add" sublevel? can we have plugins for this? should we cover this; since langgraph doesnt.
    c_80: int


class Counters(BaseModel):
    # alot of state["thing"] in the og code, so i think this is the design?
    counter: SophisticatedCounter = Field(
        default_factory=lambda: SophisticatedCounter(c_10=0, c_80=0)
    )  # or, that is because of langgraph limitation,
    # id prefer counter.update with dict.update override (Overwrite, not like that ever worked)
    simple_counter: int  # add


class Countdown(BaseModel):
    countdown: int  # add!


# has to migrate from typeddict for what? for nothing.
class Context(TypedDict):  # dataclass support? no. i mean langgraph doesnt.
    "custom RuntimeContext[MyContext] support?"

    pool: UnsophisticatedPool
    initial_rates: SophisticatedRates
    type: Literal["banner", "normal"]
    "still very convoluted logic"


# class Input(TypedDict, total=False):


## context is a hard thing
# According to https://docs.langchain.com/oss/python/concepts/context, there are three types:
#
# | type | mut | lifetime |
# | --- | --- | --- |
# |static runtime (context) | static | single run |
# |dynamic runtime (state) | mut | single run |
# |dynamic cross-convo (store) | mut | cross-conversation |
#
# now what the hell is store
### store
#
# store is used in langgraph-demo for debugging. but it can be used for more things.
# it saves every turn. every graph nodes. I use InMemoryStore, you can use psql store!
# This allows for picking the work up again after a while for example.
# a lot more versatility there.
#
### what about us? how should we handle context?
#
# in the future if wed like, we could handle context. This could be useful for lda.chat!
# i want lda.chat to be/have a meta-agent. So i could spin up ideas! a 


class ContextInput(BaseModel):
    context: Context  # final!


class how_do_i_explain_this(BaseModel):
    pity_120_available: bool = Field(default=True)


class Input(Counters, ContextInput, Countdown, how_do_i_explain_this):
    "input of the graph"


# countdown: int
# simple_counter: int
# counter: SophisticatedCounter

# context: Context


class Entity(TypedDict):
    category: Literal["1", "10", "80", "240"]
    name: str


class PoolByCategory(TypedDict):
    pool: list[str]
    category: Literal["1", "10", "80", "240"]  # stricter types
    rates: float


# context outside? what is input?
class UnsophisticatedPool(TypedDict):
    n_1: list[str]
    n_10: list[str]
    n_80: list[str]  # normal + limited
    n_240: list[str]  # special... have to do this


class Storage(BaseModel):
    "i NEED to do this?"

    storage: Annotated[list[Entity], state_field(merge_strategy="append")] = Field(
        default_factory=list
    )  # add!


class CurrentRoll(BaseModel):
    this: Entity


class PartialRates(SophisticatedRates, total=False):
    pass


class Rates(BaseModel):
    rates: Annotated[PartialRates, state_field(merge_strategy="merge_object")]  # or_!


class CurrentPools(BaseModel):
    current_pools: list[PoolByCategory]  # replace!


# holy refactory
class State(
    Counters,
    ContextInput,
    Countdown,
    CurrentRoll,
    Storage,
    Rates,
    CurrentPools,
    how_do_i_explain_this,
):
    "this forces basemodel, i used typeddict"


# countdown: int  # input carries here, should input have a bound like all(attr(input) in attr(state))? how tf do i even try to type that
# simple_counter: int  # how to signal that ts adds up? we have that.
# counter: SophisticatedCounter
# rates: SophisticatedRates  # ts needs reworking
# current_pools: list[PoolByCategory]
# this: Entity
# storage: list[
#     Entity  # how do we convey "add" root level? Annotated again? what pydantic shit can give this thing the metadata it neeeds.
# ]  # maybe for the 120 check we need to add some if any(entity.category = "240" for entity in storage), WHICH IS ASS btw.

# fuck this yo
# context: Context
