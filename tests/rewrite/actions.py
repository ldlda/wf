import random
from typing import Final

from tests.rewrite.models import (
    ContextInput,
    Countdown,
    Counters,
    CurrentPools,
    CurrentRoll,
    Entity,
    Input,
    PoolByCategory,
    Rates,
    Storage,
    how_do_i_explain_this,
)
from wf_authoring import NodeReturn, node
from wf_authoring.nodes.result import NoOutput, Nothing, outcome
from wf_core.tokens import END

# to the functions
# @node(outcomes=("ok", "end")) # breaks because of input | nothing


@node
def init(
    _inp: Input,
    # ) -> NodeReturn[Input | Nothing]:  # JUST doesnt work if the types are above
) -> None:
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
    # return Nothing()
    # return None
    # return inp


@node(outcomes=("0", "65"))
def rate_booster(c: Counters) -> NoOutput:
    """This was an edge.

    Should I implement r65 here too... i think not.

    the flow was init --rate_booster-> (65, r65), (0, r0), which outputs to the same
    rate_guarantee, which is no op.
    """
    if c.counter["c_80"] >= 65:
        return outcome("65")
    return outcome("0")


def _popped(storage: list[Entity]) -> bool:
    return any(c["category"] == "240" for c in reversed(storage))


@node
def popped(s: Storage) -> how_do_i_explain_this:
    return how_do_i_explain_this(pity_120_available=not _popped(s.storage))


# OHH so each of these MAY only only use whatever is needed? woah. i like


class CountersContext(Counters, ContextInput): ...


# this gets annoying.
class CountersContextOutputInputAhhModelType(
    CountersContext, Storage, how_do_i_explain_this
): ...


@node(outcomes=("240", "80", "10", "1"))
def pre_roll_router(c: CountersContextOutputInputAhhModelType) -> NoOutput:
    """another edge.

    the conditional router calculates which to reset to 0 (guarantee the rest)

    the flow was rate_guarantee --router-> (1 -> prep), (10 -.-> RateChange.r10 --> prep) (80 -.-> r80 --> prep), (240 -.-> r240 -> prep).
    """
    sc, ct = c.simple_counter, c.counter
    if c.context["type"] == "banner" and (
        (sc == 120 and c.pity_120_available) or (sc > 0 and sc % 240 == 0)
    ):
        return outcome("240")
    if ct.get("c_80", 0) % 80 == 0:
        return outcome("80")
    if ct.get("c_10", 0) % 10 == 0:
        return outcome("10")
    return outcome("1")


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
        r10 = br["r_10"]  # use initial rates because i dont know how this works
        r1 = 1 - r240 - r80 - r10
        return Rates.model_validate(
            {
                "rates": {
                    "r_1": r1,
                    "r_10": r10,
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
    def c80(_: Nothing) -> Counters:
        return Counters.model_validate(
            {
                "counter": {
                    "c_80": 0,
                    "c_10": 0,
                },
                "simple_counter": 0,
                # this is influenced by the add reducer.
                # its top level. it doesnt reset. its a miracle. i hate this.
            }
        )

    @node(name="counter 5* reset")
    @staticmethod
    def c10(c: Counters) -> Counters:
        c80 = c.counter["c_80"]
        return Counters.model_validate(
            {
                "counter": {"c_10": 0, "c_80": c80},  # merge with or_!
                "simple_counter": 0,
            }
        )

    @node(name="counting up")
    @staticmethod
    def c1(state: Counters) -> Counters:
        c = state.counter
        c10, c80 = c["c_10"], c["c_80"]
        return Counters(
            simple_counter=1,
            counter={"c_10": (c10 + 1) % 10, "c_80": (c80 + 1) % 80},
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


class ThisStorage(Storage, CurrentRoll): ...


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
) -> NoOutput:  # Literal["240", "80", "10", "1"] maybe you need to encode this in node returns. Literal of strings.
    return outcome(state.this["category"])


@node(name="main")
def tick(state: Countdown) -> Countdown:
    """Emit a countdown delta because State.countdown uses the add reducer."""
    return Countdown(countdown=-1)


@node(outcomes=("tick", END))
def keep_rolling(state: Countdown) -> NodeReturn[Nothing]:
    return outcome("tick") if (state.countdown or 0) > 0 else outcome(END)


# there is like no general uses for the nodes; idk tho
