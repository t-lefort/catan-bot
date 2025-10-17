import pytest


def _import_rules():
    try:
        # Contract: constants live under catan.engine.rules
        from catan.engine import rules  # type: ignore
        return rules
    except Exception:
        pytest.xfail("Module catan.engine.rules manquant (moteur non implémenté)")


def test_variant_constants_defined():
    rules = _import_rules()
    assert getattr(rules, "VP_TO_WIN", None) == 15
    assert getattr(rules, "DISCARD_THRESHOLD", None) == 9


def test_build_costs_contract():
    rules = _import_rules()
    # Représentation attendue: mapping str->dict[str,int]
    expected = {
        "road": {"BRICK": 1, "LUMBER": 1},
        "settlement": {"BRICK": 1, "LUMBER": 1, "WOOL": 1, "GRAIN": 1},
        "city": {"GRAIN": 2, "ORE": 3},
        "development": {"WOOL": 1, "GRAIN": 1, "ORE": 1},
    }
    costs = getattr(rules, "COSTS", None)
    assert isinstance(costs, dict)
    assert costs == expected

