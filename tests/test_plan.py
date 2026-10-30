import json

import pytest

from reelcraft.core import plan as P


def test_parse_time():
    assert P.parse_time(2) == 2.0
    assert P.parse_time("1:05.5") == 65.5
    assert P.parse_time("end", 9.0) == 9.0
    with pytest.raises(P.PlanError):
        P.parse_time("soon")


def test_build_orders_by_layer_then_plan_order():
    plan = P.build([{"fx": "sticker", "start": 0}, {"fx": "grade", "start": 0}, {"fx": "punch-in", "start": 0},
                    {"fx": "badge", "start": 0}])
    assert [i.name for i in plan.items] == ["punch-in", "grade", "sticker", "badge"]


def test_default_end_and_clamping_and_skip():
    plan = P.build([{"fx": "flash", "start": 1}, {"fx": "grade", "start": 2, "end": 99}, {"fx": "film", "start": 50}], duration=10)
    flash, grade = plan.items[0], plan.items[1]
    assert flash.end == pytest.approx(1.35)
    assert grade.end == 10
    assert len(plan.items) == 2 and plan.warnings


def test_errors_are_plain_language():
    with pytest.raises(P.PlanError, match="after start"):
        P.build([{"fx": "grade", "start": 3, "end": 2}])
    with pytest.raises(P.PlanError, match="no option"):
        P.build([{"fx": "grade", "colour": "x"}])
    with pytest.raises(P.PlanError, match="'fx'"):
        P.build([{"start": 1}])


def test_spec_and_file(tmp_path):
    e = P.parse_spec("kinetic-title@2-4.5 text='hello *world*' size=120")
    assert e == {"fx": "kinetic-title", "start": "2", "end": "4.5", "text": "hello *world*", "size": "120"}
    f = tmp_path / "p.json"
    f.write_text(json.dumps({"effects": [{"fx": "flash", "start": 1}]}))
    assert P.load(str(f)).items[0].name == "flash"
