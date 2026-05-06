"""port/fix of ../langgraph-demo, with all the bullshit that it has.

Constraints:
    no tapping wf_core
    try to use builtin wf_authoring.ops

also:
    fix the 120 logic now that i know
"""

# alr so we start with workflowbuilder.

from pprint import pprint
import random
from typing import Annotated, Any, Final, Literal, TypedDict


from wf_authoring.builder import WorkflowBuilder
from pydantic import BaseModel, Field

from wf_authoring import node
from wf_authoring import NodeReturn
from wf_authoring.dsl.conditions import expr, state
from wf_authoring.nodes.registry import build_registry
from wf_authoring.schemas import state_field
from wf_core.run_state import RunStatus
from wf_core.runtime.engine import execute_workflow
from wf_core.tokens import END

# i copy things over, not the greatest design but im not doing deep fixes.


class SophisticatedCounter(TypedDict):
    c_10: int  # how do i convey "add" sublevel? can we have plugins for this? should we cover this; since langgraph doesnt.
    c_80: int


class SophisticatedRates(TypedDict):
    r_1: float
    r_10: float
    r_80: float  # 0.5 sometimes, 1
    # not including 240 because ill force it by simple_counter, the pool split probably forces half, dealing w ts is ahh.
    r_240: float  # i caved


# class Input(TypedDict, total=False):


class Counters(BaseModel):
    # alot of state["thing"] in the og code, so i think this is the design?
    counter: SophisticatedCounter = Field(
        default_factory=lambda: SophisticatedCounter(c_10=0, c_80=0)
    )  # or, that is because of langgraph limitation,
    # id prefer counter.update with dict.update override (Overwrite, not like that ever worked)
    simple_counter: int  # add


class Countdown(BaseModel):
    countdown: int  # add!


class ContextInput(BaseModel):
    context: Context  # final!


class how_do_i_explain_this(BaseModel):
    pity_120_available: bool = True


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


# has to migrate from typeddict for what? for nothing.
class Context(TypedDict):  # dataclass support? no. i mean langgraph doesnt.
    "custom RuntimeContext[MyContext] support?"

    pool: UnsophisticatedPool
    initial_rates: SophisticatedRates
    type: Literal["banner", "normal"]
    "still very convoluted logic"


class Storage(BaseModel):
    "i NEED to do this?"

    storage: Annotated[list[Entity], state_field(merge_strategy="append")] = Field(
        default_factory=list
    )  # add!


class CurrentRoll(BaseModel):
    this: Entity


class ThisStorage(Storage, CurrentRoll): ...


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


gacha = WorkflowBuilder(
    name="im not hiding it no more",
    input_schema=Input,
    output_schema=Storage,  # could be State, since the OG doesnt care, ill probably dump out the list.
    state_schema=State,
    start="init",
)


class Nothing(BaseModel): ...  # variance shit IDC


# to the functions
# @node(outcomes=("ok", "end")) # breaks because of input | nothing
@node
def init(
    inp: Input,
    # ) -> NodeReturn[Input | Nothing]:  # JUST doesnt work if the types are above
) -> Input:
    # why cant use basemodel? should we convert typeddicts to basemodels? Why cant use
    """i hope that this is done by default, because langgraph DOESNT. why.

    since input and state has the same keys
    """
    # if ctx.context["type"] == 'normal' and ctx.context["initial_rates"]["r_240"] != 0:
    #     "what now" # pylint: disable=W0105
    # return (
    #     NodeReturn("ok", inp)
    #     if inp.countdown > 0
    #     else NodeReturn("end", Nothing())  # end early
    # )
    # if inp.pity_120_available and inp.context["type"] == "normal":
    #    "i doesnt care"
    return inp


# OHH so each of these MAY only only use whatever is needed? woah. i like


class CountersContext(Counters, ContextInput): ...


# this gets annoying.
class CountersContextOutputInputAhhModelType(
    CountersContext, Storage, how_do_i_explain_this
): ...


@node(outcomes=("0", "65"))
def rate_booster(c: Counters) -> NodeReturn[Nothing]:
    """This was an edge.

    Should I implement r65 here too... i think not.

    the flow was init --rate_booster-> (65, r65), (0, r0), which outputs to the same
    rate_guarantee, which is no op.
    """
    if c.counter["c_80"] >= 65:
        return NodeReturn("65", Nothing())
    return NodeReturn("0", Nothing())


def s(o: str) -> NodeReturn[Nothing]:
    return NodeReturn(o, Nothing())


def _popped(storage: list[Entity]) -> bool:
    return any(c["category"] == "240" for c in reversed(storage))


@node
def popped(s: Storage) -> how_do_i_explain_this:
    return how_do_i_explain_this(pity_120_available=_popped(s.storage))


@node(outcomes=("240", "80", "10", "1"))
def pre_roll_router(c: CountersContextOutputInputAhhModelType) -> NodeReturn[Nothing]:
    """another edge.

    the conditional router calculates which to reset to 0 (guarantee the rest)

    the flow was rate_guarantee --router-> (1 -> prep), (10 -.-> RateChange.r10 --> prep) (80 -.-> r80 --> prep), (240 -.-> r240 -> prep).
    """
    sc, ct = c.simple_counter, c.counter
    if c.context["type"] == "banner" and (
        (sc == 120 and c.pity_120_available) or (sc > 0 and sc % 240 == 0)
    ):
        return NodeReturn("240", Nothing())
    if ct.get("c_80", 0) % 80 == 0:
        return s("80")
    if ct.get("c_10", 0) % 10 == 0:
        return s("10")
    return s("1")


# now to the weeds of it. a Class!


class RateChange:
    @node(name="force 6* rating")
    @staticmethod
    def r80(r: Rates) -> Rates:
        return Rates.model_validate(
            {
                "rates": {
                    "r_1": 0,
                    "r_10": 0,
                    "r_80": r.rates["r_80"],
                    "r_240": r.rates["r_240"],
                }
            }
        )

    @node(name="force banner rating")
    @staticmethod
    def r240(_: Nothing) -> Rates:
        return Rates.model_validate(
            {"rates": {"r_1": 0, "r_10": 0, "r_80": 0, "r_240": 1}}
        )

    @node(name="force 5*+ rating")
    @staticmethod
    def r10(r: Rates) -> Rates:
        return Rates.model_validate(
            {
                "rates": {
                    "r_1": 0,
                    "r_10": r.rates["r_10"],
                    "r_80": r.rates["r_80"],
                    "r_240": r.rates["r_240"],
                }
            }
        )

    @node(name="buff 6* rating")
    @staticmethod
    def r65(state: CountersContext) -> Rates:
        c = state.counter
        assert c["c_80"] >= 65, f"routed wrongly, 80 pity currently at {c['c_80']}"
        n = c["c_80"] - 64
        rpn = n * 0.05
        br = state.context["initial_rates"]
        if state.context["type"] == "banner":
            r240 = br["r_240"] * (1 + rpn / 2)
            r80 = br["r_80"] * (1 + rpn / 2)
        else:
            r240 = 0
            r80 = br["r_80"] * (1 + rpn)

        return Rates.model_validate(
            {
                "rates": {
                    "r_1": 1 - r240 - r80 - br["r_10"],
                    "r_10": br["r_10"],
                    "r_80": r80,
                    "r_240": r240,
                }
            }
        )

    @node(name="reset rating")
    @staticmethod
    def r0(state: ContextInput) -> Rates:
        return Rates.model_validate({"rates": state.context["initial_rates"].copy()})


class CounterUp:
    @node(name="counter 6* reset")
    @staticmethod
    def c80(c: Counters) -> Counters:
        return Counters.model_validate(
            {
                "counter": {
                    "c_80": 0,
                    "c_10": 0,
                },
                "simple_counter": c.simple_counter,
            }
        )

    @node(name="counter 5* reset")
    @staticmethod
    def c10(c: Counters) -> Counters:
        return Counters.model_validate(
            {
                "counter": {"c_10": 0, "c_80": c.counter["c_80"]},  # merge with or_!
                "simple_counter": c.simple_counter,
            }
        )

    @node(name="counting up")
    @staticmethod
    def c1(state: Counters) -> Counters:
        c = state.counter
        return Counters(
            simple_counter=state.simple_counter + 1,
            counter={"c_10": (c["c_10"] + 1) % 10, "c_80": (c["c_80"] + 1) % 80},
        )


class RatesContextInput(Rates, ContextInput): ...


@node(name="prepare pool")
def prep(state: RatesContextInput) -> CurrentPools:
    r = state.rates
    p = state.context["pool"]
    t: Final[tuple[tuple[str, str, str], ...]] = (  # greatest hack
        ("1", "r_1", "n_1"),
        ("10", "r_10", "n_10"),
        ("80", "r_80", "n_80"),
        ("240", "r_240", "n_240"),
    )
    pbc = [PoolByCategory(pool=p[pc], category=ty, rates=r[pr]) for ty, pr, pc in t]
    # print(pbc)
    return CurrentPools.model_validate({"current_pools": pbc})


@node
def roll(state: CurrentPools) -> ThisStorage:
    r = state.current_pools
    (t,) = random.choices(r, weights=[*map(lambda p: p["rates"], r)])
    this = Entity(category=t["category"], name=random.choice(t["pool"]))
    return ThisStorage.model_validate(
        {
            "this": this,
            "storage": [this],  # I NEED MERGE
        }
    )


@node(outcomes=("240", "80", "10", "1"))  # missed this! good job.
def post_roll_router(
    state: CurrentRoll,
) -> NodeReturn[
    Nothing
]:  # Literal["240", "80", "10", "1"] maybe you need to encode this in node returns. Literal of strings.
    return NodeReturn(state.this["category"], Nothing())


@node(name="main")
def tick(state: Countdown) -> Countdown:
    return Countdown(countdown=state.countdown - 1)


@node(outcomes=("tick", END))
def keep_rolling(state: Countdown) -> NodeReturn[Nothing]:
    return s("tick") if (state.countdown or 0) > 0 else s(END)


# could be @graph.(something combining node and use)...

gacha.use(init)
gacha.use(tick, id="tick") # itd use main
counter_up = gacha.use(CounterUp.c1, id="counter_up")  # 0 base to 1 base probably
rate_up = gacha.use(RateChange.r65, id="rate_up")
rate_same = gacha.use(RateChange.r0, id="rate_same")
r_10 = gacha.use(RateChange.r10, id="r_g10")
gacha.use(RateChange.r80, id="r_g80")
gacha.use(RateChange.r240, id="r_gs")
prepare_pool = gacha.use(prep)
gacha.use(roll)
c_80 = gacha.use(CounterUp.c80, id="c_80")
gacha.use(CounterUp.c10, id="c_10")
gacha.condition(  # condition dont ignore id; you can...
    id="keep_rolling", check=expr(state("countdown")) > 0
)  # replaces keep_rolling
# Outcome is currently hidden from the docs (there is none), outcome_map is insane, should we have it
gacha.connect("init", "ok", "keep_rolling")
gacha.connect("keep_rolling", "true", "tick")
gacha.connect("keep_rolling", "false", END)

gacha.connect("tick", "ok", "counter_up")
gacha.use(rate_booster, id="rate_booster")

gacha.connect("counter_up", "ok", "rate_booster")
gacha.connect("rate_booster", "0", rate_same)
gacha.connect("rate_booster", "65", rate_up)
gacha.use(pre_roll_router, id="router")

gacha.connect("rate_up", "ok", "router")
gacha.connect("rate_same", "ok", "router")
preroll_routes = gacha.branch(
    "router",
    {
        "240": "r_gs",
        "80": "r_g80",
        "10": r_10,
        "1": "prepare_pool",
    },
)
print(preroll_routes)
gacha.connect(prepare_pool, "ok", "roll")
gacha.connect("r_gs", "ok", "prepare_pool")
gacha.connect(preroll_routes["80"], "ok", prepare_pool)
gacha.connect("r_g10", "ok", prepare_pool)

gacha.connect("roll", "ok", "post_roll_router")  # missed this! good job
gacha.use(post_roll_router, id="post_roll_router")
reset_avail = gacha.use(popped, id="reset_avail")
gacha.connect(reset_avail, "ok", c_80)

# missed this!
gacha.branch(
    "post_roll_router",
    {
        "240": "reset_avail",
        "80": "c_80",
        "10": "c_10",
        "1": "keep_rolling",
    },
)

gacha.connect(c_80, "ok", "keep_rolling")
gacha.connect("c_10", "ok", "keep_rolling")

# there is like no general uses for the nodes; idk tho

context: Final[Context] = {
    "initial_rates": {
        "r_1": 0.912,
        "r_10": 0.08,
        "r_80": 0.004,
        "r_240": 0.004,
    },
    "pool": {
        "n_1": ["Akekuri", "Catcher", "Flourite", "Estella", "Antal"],
        "n_10": [
            "Perlica",
            "Arclight",
            "Avywenna",
            "Da Pan",
            "Chen Qianyu",
            "Wulfgard",
            "Xaihi",
            "Snowshine",
            "Alesh",
        ],
        "n_80": [
            "Rossi",
            "Tangtang",
            # "Yvonne",
            # "Gilberta",
            # "Laevatain",
            "Ember",
            "Lifeng",
            "Ardelia",
            "Last Rite",
            "Pogranichnik",
        ],
        "n_240": [  # normal or banner / logic is hella flawed lowk ong
            # "Rossi",
            # "Tangtang",
            "Zhuang Fangyi",
        ],
    },
    "type": "banner",
}


def build_input_lite(
    rolling: int,
    rolled_previously: int = 0,
    until_5: int = 10,
    until_6: int = 80,
    good_stuff: bool = False,
) -> dict[str, Any]:
    if not 0 < until_5 <= 10:
        print(f"{until_5 = } invalid, idc")
    if not 0 < until_6 <= 80:
        print(f"{until_6 = } invalid, running anyways")
    return {
        "countdown": rolling,
        "simple_counter": rolled_previously,
        "counter": {
            "c_10": 10 - until_5,
            "c_80": 80 - until_6,
        },
        "pity_120_available": not good_stuff,
    }


def build_input(context: Context):
    def dec(
        rolling: int,
        rolled_previously: int = 0,
        until_5: int = 10,
        until_6: int = 80,
        good_stuff: bool = False,
    ) -> Input:
        r = build_input_lite(rolling, rolled_previously, until_5, until_6, good_stuff)
        return Input.model_validate(r | {"context": context})

    return dec


def execute(graph: WorkflowBuilder, input: Input):
    c = graph.compile()
    r = build_registry(*(graph.node_specs.values()))
    i = input.model_dump()
    pprint(i)
    pprint(c)
    pprint(r)
    return execute_workflow(c, i, r)


# twice in a row! it took 100+ and a miss tho


def test():
    d = execute(
        gacha,
        build_input(context)(
            20,
            rolled_previously=240 - 135,
            until_5=5,
            until_6=73,
            good_stuff=False,  # lets pretend
        ),
    )
    assert d.status == RunStatus.COMPLETED, "oops"
    state = State.model_validate(d.state)
    assert any(i["name"] in context["pool"]["n_240"] for i in state.storage)
    pprint(state.storage)


if __name__ == "__main__":
    test()
