import re

import pytest

from es_optimizer import roles


def test_bundled_roles_load_and_combine():
    composites = roles.shared_metrics(None)
    for name in roles.available_roles(None):
        request = roles.combine([roles.load_role(name, None)], composites)
        assert request.weights and abs(sum(request.weights.values()) - 1) < 1e-9, name


def test_scavenger():
    request = roles.combine([roles.load_role("scavenger", None)], roles.shared_metrics(None))
    assert request.role.combat is False
    assert request.must_have == ["tractor beam"]
    assert request.reverse_thrust == "balanced"
    assert not request.forbid_tags        # damage weapons are allowed, just not valued
    # should 3 + 2, emphasize cargo at 2 × 3 = 6, may push force at 0.25 × 2 = 0.5: total 11.5.
    assert request.weights["cargo space"] == pytest.approx(6 / 11.5)
    assert request.weights["push force"] == pytest.approx(0.5 / 11.5)
    assert "weapon value" not in request.weights


def test_explicit_emphasis_and_bonus_weights():
    r = roles.parse_role('[should]\n"max speed" = 1\n[must]\nemphasize = { "cargo space" = 3 }\n'
                         '[may]\nbonus = { "push force" = 1 }', "r")
    assert roles.combine([r], {}).weights == pytest.approx({"max speed": 0.2, "cargo space": 0.6, "push force": 0.2})


def test_combining_roles():
    a = roles.parse_role('[ship]\ncombat = false\n[must]\nmin = { "cargo space" = 50 }\n[should]\n"cargo space" = 1', "a")
    b = roles.parse_role('[ship]\nhero = true\nfight = "escort"\n[must]\nmin = { "cargo space" = 80 }\n'
                         'reverse_thrust = "nimble"\n[should]\n"max speed" = 3\n"turn rate" = 1', "b")
    request = roles.combine([a, b], {})
    assert request.role.combat is False and request.role.hero is True
    assert request.must_min == {"cargo space": 80}
    assert request.reverse_thrust == "nimble"
    # Each role counts equally: a's single weight is 0.5, b's 3:1 split shares the other 0.5.
    assert request.weights == pytest.approx({"cargo space": 0.5, "max speed": 0.375, "turn rate": 0.125})


@pytest.mark.parametrize("text, message", [
    ('[ship]\ncombt = true', "unknown [ship] setting"),
    ('[ship]\ngoal = "kill"', "goal must be one of"),
    ('[outfits]\nforbid = ["lasers"]', "unknown tag"),
    ('[may]\nforbid = ["missile"]', "outfit tags go in [outfits]"),
    ('[must]\nreverse_thrust = "fast"', "reverse_thrust must be"),
    ('[sholud]\nx = 1', "unknown section"),
])
def test_role_errors_are_helpful(text, message):
    with pytest.raises(roles.RoleError, match=re.escape(message)):
        roles.parse_role(text, "bad")


def test_conflicts():
    a = roles.parse_role('[must]\nmin = { "cargo space" = 50 }\n[should]\n"cargo space" = 1', "a")
    b = roles.parse_role('[must]\nmax = { "cargo space" = 10 }\n[should]\n"cargo space" = 1', "b")
    with pytest.raises(roles.RoleError, match="conflict"):
        roles.combine([a, b], {})
    c = roles.parse_role('[ship]\ngoal = "disable"\n[should]\nx = 1', "c")
    d = roles.parse_role('[ship]\ngoal = "destroy"\n[should]\nx = 1', "d")
    with pytest.raises(roles.RoleError, match="disagree"):
        roles.combine([c, d], {})
    with pytest.raises(roles.RoleError, match="one to three"):
        roles.combine([a, a, a, a], {})
