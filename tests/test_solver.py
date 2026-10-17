from pathlib import Path

import pytest

from es_optimizer import gamedata, roles, solver
from es_optimizer.storage import Settings

GAME = '''
ship "Boat"
	attributes
		category "Light Warship"
		mass 100
		drag 2
		"heat dissipation" .8
		"outfit space" 100
		"weapon capacity" 30
		"engine capacity" 30
		"cargo space" 50
		shields 1000
		hull 500
		"fuel capacity" 300
	gun 0 0
	turret 0 0

outfit "Engine"
	category "Engines"
	mass 10
	"outfit space" -10
	"engine capacity" -10
	thrust 5
	turn 100

outfit "Big Engine"
	category "Engines"
	mass 20
	"outfit space" -20
	"engine capacity" -20
	thrust 12
	turn 200

outfit "Reactor"
	category "Power"
	mass 10
	"outfit space" -10
	"energy generation" 2
	"heat generation" 1

outfit "Gun"
	category "Guns"
	mass 5
	"outfit space" -10
	"weapon capacity" -10
	"gun ports" -1
	weapon
		reload 10
		velocity 20
		lifetime 30
		"firing energy" 5
		"firing heat" 2
		"hull damage" 20

outfit "Cargo Pod"
	category "Systems"
	"outfit space" -10
	"cargo space" 10

outfit "Big Pod"
	category "Systems"
	"outfit space" -24
	"cargo space" 30

outfit "Shield Gen"
	category "Systems"
	mass 5
	"outfit space" -5
	"shield generation" .5
	"shield energy" .2

outfit "Lucky Charm"
	category "Unique"
	unique 1
	"cargo space" 500

outfitter "Shop"
	"Engine"
	"Big Engine"
	"Reactor"
	"Gun"
	"Cargo Pod"
	"Big Pod"
	"Shield Gen"
	"Lucky Charm"
'''


@pytest.fixture
def game(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "test.txt").write_text(GAME)
    return gamedata.load(tmp_path)


def request(text: str):
    base = ('[ship]\nneeds_drives = false\nneeds_ramscoop = false\nneeds_anti_missile = false\nneeds_regen = false\n')
    return roles.combine([roles.parse_role(base + text, "test")], {})


def test_optimizes_and_every_check_passes(game):
    req = request('[should]\n"cargo space" = 1')
    result = solver.optimize(game, game.hulls["Boat"], req, Settings(), seconds_per_solve=5)
    assert result.status == "optimized"
    assert not result.design.failed
    # Cargo is maximized: the hull keeps only what it needs to move (one Engine), the rest is 3 Big Pods (the
    # space-efficient ones) and a Cargo Pod.
    assert result.design.outfits.get("Big Pod", 0) == 3 and result.design.outfits.get("Cargo Pod", 0) == 1
    assert result.design.metrics["cargo space"] == 150


def test_firepower_needs_power(game):
    req = request('[should]\n"hull dps" = 1')
    result = solver.optimize(game, game.hulls["Boat"], req, Settings(), seconds_per_solve=5)
    assert result.status == "optimized" and not result.design.failed
    assert result.design.outfits.get("Gun") == 1          # one gun port
    assert result.design.outfits.get("Reactor", 0) >= 1   # a combat ship must power its weapons


def test_infeasible_reports_blocker(game):
    req = request('[should]\n"cargo space" = 1\n[must]\nmin = { "cargo space" = 1000 }')
    result = solver.optimize(game, game.hulls["Boat"], req, Settings(), seconds_per_solve=5)
    assert result.status == "infeasible"
    assert result.blockers == ["must: cargo space ≥ 1000"]


def test_blocked_outfits_are_not_used(game):
    req = request('[should]\nacceleration = 1')
    result = solver.optimize(game, game.hulls["Boat"], req, Settings(blocked_outfits={"Big Engine"}),
                             seconds_per_solve=5)
    assert "Big Engine" not in result.design.outfits


def test_scale_scores_against_stock_ships():
    scale = solver.Scale([10.0, 20.0, 30.0, 40.0])
    assert scale.score(0) == 0
    assert scale.score(20) == pytest.approx(0.5)
    assert scale.score(25) == pytest.approx(0.625)
    assert scale.score(40) == pytest.approx(1.0)
    assert scale.score(80) == pytest.approx(1 + solver.TAIL_SLOPE)       # diminishing above the best
    assert all(scale.slope(v) > 0 for v in (0, 5, 20, 40, 100))
    assert scale.describe(25) == "beats 2 of 4 stock ships"
    assert solver.Scale(ideal=50.0).score(25) == 0.5


def test_starts_cover_routes_and_budgets(game):
    composites = {"pick": {"best_of": ["cargo space", "acceleration"]}}
    base = '[ship]\nneeds_drives = false\nneeds_ramscoop = false\nneeds_anti_missile = false\nneeds_regen = false\n'
    req = roles.combine([roles.parse_role(base + 'weapons_budget = [0.8, 1.0]\nengines_budget = [1.0, 1.0]\n'
                                          '[should]\npick = 1', "test")], composites)
    result = solver.optimize(game, game.hulls["Boat"], req, Settings(), seconds_per_solve=2, polish_seconds=5)
    assert result.status == "optimized" and not result.design.failed
    labels = [label for label, _ in result.starts]
    assert labels == ["pick: cargo space, weapons ≤ 100%, engines ≤ 100%",
                      "pick: cargo space, weapons ≤ 80%, engines ≤ 100%",
                      "pick: acceleration, weapons ≤ 100%, engines ≤ 100%",
                      "pick: acceleration, weapons ≤ 80%, engines ≤ 100%"]
    assert result.design.score == max(result.design.route_scores)


def test_balance_shares(game):
    from es_optimizer import calculator
    ship = calculator.build(game, game.hulls["Boat"], {"Engine": 1, "Gun": 1, "Cargo Pod": 2})
    b = solver.balance(game, ship)
    assert b["weapon capacity used"] == pytest.approx(10 / 30)
    assert b["engine capacity used"] == pytest.approx(10 / 30)
    assert b["outfit space: engines"] == pytest.approx(0.1)
    assert b["outfit space: weapons"] == pytest.approx(0.1)
    assert b["outfit space: other"] == pytest.approx(0.2)
    assert b["outfit space: free"] == pytest.approx(0.6)


def test_unique_outfits_only_for_hero_ships(game):
    plain = solver.candidates(game, game.hulls["Boat"], Settings(), request('[should]\n"cargo space" = 1'))
    hero = solver.candidates(game, game.hulls["Boat"], Settings(),
                             request('hero = true\n[should]\n"cargo space" = 1'))
    assert "Lucky Charm" not in {o.name for o in plain}
    assert "Lucky Charm" in {o.name for o in hero}


def test_product_term_rewards_balance():
    req = roles.combine([roles.parse_role('[metrics.m]\ncombine = "product"\n"turn rate" = 1\nacceleration = 1\n'
                                          '[should]\nm = 1', "test")], {})
    scales = {"turn rate": solver.Scale(ideal=100.0), "acceleration": solver.Scale(ideal=100.0)}
    scorer = solver.Scorer(req, scales)
    balanced = scorer.route_scores({"turn rate": 50.0, "acceleration": 50.0})[0]
    lopsided = scorer.route_scores({"turn rate": 99.0, "acceleration": 1.0})[0]
    assert balanced == pytest.approx(0.5) and lopsided < 0.1
    slopes = scorer.term_slopes("m", {"turn rate": 99.0, "acceleration": 1.0})
    assert slopes["acceleration"] > slopes["turn rate"]       # the weak part is where the gain is


def test_polish_strips_useless_outfits_and_swaps_groups(game):
    from es_optimizer import calculator
    hull = game.hulls["Boat"]
    req = request('[should]\n"cargo space" = 1')
    pool = solver.candidates(game, hull, Settings(), req)
    bounds = solver._upper_bounds(hull, pool)
    scorer = solver.Scorer(req, {"cargo space": solver.Scale(ideal=150.0)})
    judge = lambda o, ship=None: solver.evaluate_design(game, hull, o, req, scorer, False, None, ship)
    # Nine small pods fill the hull: no single swap fits a Big Pod, but three small ones out for one Big Pod do.
    start = judge({"Engine": 1, "Cargo Pod": 9})
    polished, moves = solver.polish(game, hull, pool, bounds, start, judge, float("inf"))
    assert polished.outfits == {"Engine": 1, "Big Pod": 3, "Cargo Pod": 1}
    # A Reactor adds nothing to cargo: stripped.
    start = judge({"Engine": 1, "Big Pod": 3, "Reactor": 1})
    polished, _ = solver.polish(game, hull, pool, bounds, start, judge, float("inf"))
    assert "Reactor" not in polished.outfits


def test_weapon_needs_energy_for_one_shot(game):
    from es_optimizer import calculator
    role = calculator.Role(combat=False, needs_drives=False, needs_ramscoop=False, needs_anti_missile=False)
    check = lambda outfits: next(c for c in calculator.evaluate(calculator.build(game, game.hulls["Boat"], outfits),
                                                                role) if c.name == "Energy per shot")
    # No battery: one shot (5 energy) must fit in one frame of generation (2 per Reactor).
    assert check({"Engine": 1, "Gun": 1, "Reactor": 1}).passed is False
    assert check({"Engine": 1, "Gun": 1, "Reactor": 3}).passed is True


def test_regeneration_is_required_by_default(game):
    req = roles.combine([roles.parse_role('[ship]\nneeds_drives = false\nneeds_ramscoop = false\n'
                                          'needs_anti_missile = false\n[should]\n"cargo space" = 1', "t")], {})
    result = solver.optimize(game, game.hulls["Boat"], req, Settings(), seconds_per_solve=2, polish_seconds=5)
    assert result.status == "optimized" and not result.design.failed
    assert result.design.outfits.get("Shield Gen") == 1
    assert any(c.name == "Regeneration" and c.passed for c in result.design.checks)


def test_firepower_fires(game):
    req = request('[should]\n"hull dps" = 1')
    result = solver.optimize(game, game.hulls["Boat"], req, Settings(), seconds_per_solve=2, polish_seconds=5)
    assert result.design.outfits.get("Gun") == 1
    assert result.design.outfits.get("Reactor", 0) >= 3        # one shot needs 5 energy, no battery


def test_parallel_plan(monkeypatch):
    monkeypatch.setattr(solver, "available_cpus", lambda: 24)          # Ryzen 9 3900X: 12 cores, 24 threads
    assert solver.plan_parallelism(12) == (12, 2)
    assert solver.plan_parallelism(4) == (4, 6)
    monkeypatch.setattr(solver, "available_cpus", lambda: 4)
    assert solver.plan_parallelism(12) == (2, 2)
    assert solver.plan_parallelism(12, jobs=1) == (1, 4)
    monkeypatch.setattr(solver, "available_cpus", lambda: 1)
    assert solver.plan_parallelism(12) == (1, 1)


def test_parallel_and_serial_both_work(game):
    req = request('[should]\n"cargo space" = 1')
    for jobs in (1, 2):
        result = solver.optimize(game, game.hulls["Boat"], req, Settings(), seconds_per_solve=2, polish_seconds=4,
                                 jobs=jobs)
        assert result.status == "optimized" and not result.design.failed and result.jobs == jobs
        assert result.design.metrics["cargo space"] == 150


def test_balance_counts_weapon_support_as_weapons(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "t.txt").write_text(GAME + '''
outfit "Lasing Generator"
	category "Systems"
	"outfit space" -30
	"lasing power" 3
outfit "Laser"
	category "Guns"
	"outfit space" -10
	"weapon capacity" -10
	"gun ports" -1
	"lasing power" -2
	weapon
		reload 1
		lifetime 1
		velocity 500
		"hull damage" 1
''')
    from es_optimizer import calculator
    g = gamedata.load(tmp_path)
    ship = calculator.build(g, g.hulls["Boat"], {"Engine": 1, "Laser": 1, "Lasing Generator": 1})
    b = solver.balance(g, ship)
    assert b["outfit space: weapons"] == pytest.approx(0.4) and b["outfit space: other"] == 0
