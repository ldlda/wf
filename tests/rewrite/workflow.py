from tests.rewrite.actions import (
    CounterUp,
    RateChange,
    init,
    popped,
    post_roll_router,
    pre_roll_router,
    prep,
    roll,
    tick,
)
from tests.rewrite.models import Input, State, Storage
from wf_authoring.builder import WorkflowBuilder
from wf_authoring.dsl.conditions import expr, state
from wf_core.tokens import END

# alr so we start with workflowbuilder.

gacha = WorkflowBuilder(
    name="im not hiding it no more",
    input_schema=Input,
    output_schema=Storage,  # could be State, since the OG doesnt care, ill probably dump out the list.
    state_schema=State,
)
"example workflow"

gacha.use(tick, id="tick")  # itd use main if we dont have id
counter_up = gacha.use(CounterUp.c1, id="counter_up")  # 0 base to 1 base probably
rate_up = gacha.use(RateChange.r65, id="rate_up")
rate_same = gacha.use(RateChange.r0, id="rate_same")
r_10 = gacha.use(RateChange.r10, id="r_g10")
gacha.use(RateChange.r80, id="r_g80")
gacha.use(RateChange.r240, id="r_gs")
c_80 = gacha.use(CounterUp.c80, id="c_80")
gacha.use(CounterUp.c10, id="c_10")
gacha.condition(  # condition dont ignore id; you can...
    id="keep_rolling", check=expr(state("countdown")) > 0
)  # replaces keep_rolling
# Outcome is currently hidden from the docs (there is none), outcome_map is insane, should we have it
init_ref, _ = gacha.connect(init, "ok", "keep_rolling")
gacha.connect("keep_rolling", "true", "tick")
gacha.connect("keep_rolling", "false", END)

gacha.connect("tick", "ok", "counter_up")
# gacha.use(rate_booster, id="rate_booster")

gacha.connect("counter_up", "ok", "rate_booster")
# gacha.connect("rate_booster", "0", rate_same)
# gacha.connect("rate_booster", "65", rate_up)
rate_route = gacha.route(
    state("counter.c_80").ge(65),
    {
        True: rate_up,
        False: rate_same,
    },
    id = "rate_booster"
)

gacha.use(pre_roll_router, id="router")

gacha.connect("rate_up", "ok", "router")
gacha.connect("rate_same", "ok", "router")
preroll_routes = gacha.branch(
    "router",
    {
        "240": "r_gs",
        "80": "r_g80",
        "10": r_10,
        "1": prep,
    },
)
prepare_pool = preroll_routes["1"]
_, roll_ref = gacha.connect(prepare_pool, "ok", roll)
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
gacha.set_entry_point(init_ref)
