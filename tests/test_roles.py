import re

import pytest

from es_optimizer import roles


def test_bundled_roles_load_and_combine():
    composites = roles.shared_metrics(None)
    for name in roles.available_roles(None):
        request = roles.combine([roles.load_role(name, None)], composites)
        assert request.weights and abs(sum(abs(v) for v in request.weights.values()) - 1) < 1e-9, name


def test_scavenger():
    request = roles.combine([roles.load_role("scavenger", None)], roles.shared_metrics(None))
    assert request.role.combat is False
    assert request.must_have == ["tractor beam"]
    assert request.reverse_thrust == "balanced"
    assert not request.forbid_tags        # damage weapons are allowed, just not valued
    # should: survivability 60%, maneuverability 40%; emphasize cargo takes 50%; may push force takes 10%.
    assert request.weights["cargo space"] == pytest.approx(0.45)
    assert request.weights["push force"] == pytest.approx(0.10)
    assert request.weights["turn rate"] == pytest.approx(0.4 * 0.5 * 0.9 / 2)
    assert "weapon value" not in request.weights


def test_explicit_emphasis_and_bonus_weights():
    r = roles.parse_role('[should]\n"max speed" = 1\n[must]\nemphasize = { "cargo space" = 0.6 }\n'
                         '[may]\nbonus = { "push force" = 0.2 }', "r")
    # Steps: max speed 100% -> 40% + cargo 60% -> × 0.8, + push force 20%.
    assert roles.combine([r], {}).weights == pytest.approx({"max speed": 0.32, "cargo space": 0.48, "push force": 0.2})


def test_should_not_share_does_not_depend_on_should_size():
    one = roles.parse_role('[should]\n"cargo space" = 1\n[should_not]\nhave = ["reverse thrust"]', "one")
    many = roles.parse_role('[should]\n"cargo space" = 5\n"max speed" = 1\n"bunks" = 1\n'
                            '[should_not]\nhave = ["reverse thrust"]', "many")
    assert roles.combine([one], {}).weights["reverse thrust"] == pytest.approx(-0.2)
    assert roles.combine([many], {}).weights["reverse thrust"] == pytest.approx(-0.2)


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


def test_must_not_overrides_defaults_and_should_not_penalizes():
    request = roles.combine([roles.load_role("peaceful-freighter", None)], roles.shared_metrics(None))
    assert request.must_not == ["anti-missile", "jump drive"]
    assert request.role.needs_anti_missile is False
    assert request.role.excluded_drives == {"jump drive"}
    assert request.weights["reverse thrust"] < 0 < request.weights["cargo space"]
    assert sum(abs(v) for v in request.weights.values()) == pytest.approx(1)


def test_deprioritize_cuts_weight_from_other_roles():
    fast = roles.parse_role('[should]\nspeed = 1', "fast")
    slow = roles.parse_role('[should]\n"cargo space" = 1\ndeprioritize = ["speed"]', "slow")
    composites = {"speed": {"max speed": 2, "acceleration": 1}}
    plain = roles.combine([fast], composites).weights
    both = roles.combine([fast, slow], composites).weights
    # Before deprioritizing, max speed would be half its single-role weight, cargo space 0.5.
    assert both["max speed"] / both["cargo space"] == pytest.approx(
        plain["max speed"] / 2 * roles.DEPRIORITIZE_FACTOR / 0.5)


def test_must_and_must_not_conflict():
    a = roles.parse_role('[must]\nhas = ["ramscoop"]\n[should]\nx = 1', "a")
    b = roles.parse_role('[must_not]\nhave = ["ramscoop"]\n[should]\nx = 1', "b")
    with pytest.raises(roles.RoleError, match="must have and must not have ramscoop"):
        roles.combine([a, b], {})
