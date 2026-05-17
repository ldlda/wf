"""port/fix of ../langgraph-demo, with all the bullshit that it has.

Constraints:
    no tapping wf_core
    try to use builtin wf_authoring.ops
"""

from itertools import islice
import json
from pprint import pprint
from typing import Any

from tests.rewrite.context import context
from tests.rewrite.models import (
    Context,
    Input,
    State,
)
from tests.rewrite.workflow import gacha
from wf_core.run_state import RunStatus


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


# twice in a row! it took 100+ and a miss tho


def test():
    assert 240 - 135 + 20 >= 120, "my math!"
    d = gacha.execute(
        build_input(context)(
            20,  # lets be optimistic
            rolled_previously=240 - 135,
            until_5=5,
            until_6=73,
            good_stuff=False,  # lets pretend
        ).model_dump()
    )
    assert d.status == RunStatus.COMPLETED, "oops"
    state = State.model_validate(d.state)
    assert any(
        i["name"] in context["pool"]["n_240"]
        for i in islice(state.storage, 120 - (240 - 135))
    ), "pity logic failed"
    pprint(state.storage)
    # pprint(gacha.compile().edges)
    # pprint(gacha.compile().nodes)


if __name__ == "__main__":
    test()
