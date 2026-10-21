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
    # (The evasive route: the durable route also applies its tank effects.)
    request.weights = next(r.weights for r in request.routes if r.label == "survivability: evasive")
    assert request.weights["cargo space"] == pytest.approx(0.45)
    assert request.weights["push force"] == pytest.approx(0.10)
    assert request.weights["maneuverability"] == pytest.approx(0.4 * 0.5 * 0.9)   # a product: one term
    assert request.products["maneuverability"] == {"turn rate": 1.0, "acceleration": 1.0}
    assert {"turn rate", "acceleration"} <= set(request.metrics)
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
    assert "reverse thrust" not in request.weights and request.weights["cargo space"] > 0
    assert not roles.asks_for_reverse(request)
    assert roles.asks_for_reverse(roles.combine([roles.load_role("scavenger", None)], roles.shared_metrics(None)))
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


def test_best_of_composite_gives_one_route_per_branch():
    composites = {"survivability": {"best_of": ["durable", "evasive"]},
                  "durable": {"shield regen": 2, "hull repair": 1}, "evasive": {"agility": 1}}
    r = roles.parse_role('[should]\nsurvivability = 1\n"cargo space" = 1', "test")
    request = roles.combine([r], composites)
    assert [route.label for route in request.routes] == ["survivability: durable", "survivability: evasive"]
    assert request.routes[0].weights == pytest.approx({"shield regen": 1 / 3, "hull repair": 1 / 6, "cargo space": 0.5})
    assert request.routes[1].weights == pytest.approx({"agility": 0.5, "cargo space": 0.5})
    assert request.weights == request.routes[0].weights
    assert set(request.metrics) == {"shield regen", "hull repair", "cargo space", "agility"}


def test_naming_a_branch_picks_the_route():
    composites = {"survivability": {"best_of": ["durable", "evasive"]},
                  "durable": {"shield regen": 1}, "evasive": {"agility": 1}}
    request = roles.combine([roles.parse_role("[should]\ndurable = 1", "test")], composites)
    assert len(request.routes) == 1 and request.routes[0].label == ""
    assert request.weights == {"shield regen": 1.0}


def test_bad_best_of_is_rejected():
    with pytest.raises(roles.RoleError, match="best_of"):
        roles.parse_role('[metrics.x]\nbest_of = ["a"]', "test")


def test_budget_ranges_combine_by_overlap():
    a = roles.parse_role("[ship]\nweapons_budget = [0.85, 1.0]\n[should]\nspeed = 1", "a")
    b = roles.parse_role("[ship]\nweapons_budget = [0.5, 0.9]\nengines_budget = [0.2, 0.6]\n[should]\nspeed = 1", "b")
    request = roles.combine([a, b], {})
    assert request.weapons_budget == (0.85, 0.9)
    assert request.engines_budget == (0.2, 0.6)
    assert roles.combine([a], {}).engines_budget == roles.DEFAULT_ENGINES_BUDGET
    with pytest.raises(roles.RoleError, match="weapons_budget"):
        roles.parse_role("[ship]\nweapons_budget = [0.9, 0.5]", "c")


def test_product_composite():
    r = roles.parse_role('[metrics.agile]\ncombine = "product"\n"turn rate" = 2\nacceleration = 1\n'
                         '[should]\nagile = 1\n"cargo space" = 1', "test")
    request = roles.combine([r], {})
    assert request.weights == pytest.approx({"agile": 0.5, "cargo space": 0.5})
    assert request.products == {"agile": {"turn rate": 2.0, "acceleration": 1.0}}
    with pytest.raises(roles.RoleError, match="product"):
        roles.parse_role('[metrics.x]\ncombine = "product"\n"turn rate" = 1', "test")
    with pytest.raises(roles.RoleError, match="combine"):
        roles.parse_role('[metrics.x]\ncombine = "max"\n"turn rate" = 1\nacceleration = 1', "test")


def test_unique_outfits_default_to_hero_ships():
    plain = roles.parse_role("[should]\nspeed = 1", "a")
    hero = roles.parse_role("[ship]\nhero = true\n[should]\nspeed = 1", "b")
    allowed = roles.parse_role("[ship]\nunique_outfits = true\n[should]\nspeed = 1", "c")
    refused = roles.parse_role("[ship]\nhero = true\nunique_outfits = false\n[should]\nspeed = 1", "d")
    assert not roles.combine([plain], {}).unique_outfits
    assert roles.combine([hero], {}).unique_outfits
    assert roles.combine([allowed], {}).unique_outfits
    assert not roles.combine([refused], {}).unique_outfits


def test_request_level_emphasis_and_deprioritization():
    composites = {"firepower": {"weapon value": 1}, "survivability": {"shield regen": 1}}
    r = roles.parse_role("[should]\nfirepower = 1\nsurvivability = 1", "test")
    base = roles.combine([r], composites).weights
    assert base == pytest.approx({"weapon value": 0.5, "shield regen": 0.5})
    focused = roles.combine([r], composites, emphasize=["firepower"], deprioritize=["survivability"]).weights
    assert focused["weapon value"] > 0.9 and focused["shield regen"] < 0.1
    assert sum(focused.values()) == pytest.approx(1)


def test_route_effects_and_emphasis_override():
    composites = {"survivability": {"best_of": ["durable", "evasive"]},
                  "durable": {"shield regen": 1.0, "when_chosen": {"scale": {"agility": 0.25},
                                                                    "bonus": {"pull force": 0.1}}},
                  "evasive": {"max speed": 1.0}}
    r = roles.parse_role("[should]\nsurvivability = 1\nagility = 1", "test")
    durable, evasive = roles.combine([r], composites).routes
    assert evasive.weights == pytest.approx({"max speed": 0.5, "agility": 0.5})
    assert durable.weights["agility"] == pytest.approx(0.2 * 0.9)      # 0.5 × 0.25, renormalized, then × 0.9
    assert durable.weights["pull force"] == pytest.approx(0.1)
    kept = roles.combine([r], composites, emphasize=["agility"]).routes[0]
    assert kept.weights["agility"] == pytest.approx(0.5 * 0.9)          # emphasized (50%): not cut, only the bonus
    parsed = roles.parse_role('[metrics.x]\na = 1\nwhen_chosen = { scale = { b = 0.5 } }', "t").composites["x"]
    assert parsed["when_chosen"] == {"scale": {"b": 0.5}, "bonus": {}}


def test_min_percentile_and_emphasis_shares():
    r = roles.parse_role('[must]\nmin_percentile = { "turn rate" = 0.05 }\n[should]\nspeed = 1', "t")
    assert r.must_percentile == {"turn rate": 0.05}
    assert roles.combine([r], {}).must_percentile == {"turn rate": 0.05}
    with pytest.raises(roles.RoleError, match="share between 0 and 1"):
        roles.parse_role('[must]\nmin_percentile = { "turn rate" = 5 }', "t")
    w = roles.combine([roles.parse_role("[should]\nagility = 1\n\"cargo space\" = 1", "t")], {},
                      emphasize=["agility=0.2"]).weights
    assert w == pytest.approx({"agility": 0.2, "cargo space": 0.8})     # exactly its share
    with pytest.raises(roles.RoleError, match="metric=share"):
        roles.combine([r], {}, emphasize=["agility=lots"])
