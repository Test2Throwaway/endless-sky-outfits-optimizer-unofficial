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

outfitter "Shop"
	"Engine"
	"Big Engine"
	"Reactor"
	"Gun"
	"Cargo Pod"
'''


@pytest.fixture
def game(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "test.txt").write_text(GAME)
    return gamedata.load(tmp_path)


def request(text: str):
    base = ('[ship]\nneeds_drives = false\nneeds_ramscoop = false\nneeds_anti_missile = false\n')
    return roles.combine([roles.parse_role(base + text, "test")], {})


def test_optimizes_and_every_check_passes(game):
    req = request('[should]\n"cargo space" = 1')
    result = solver.optimize(game, game.hulls["Boat"], req, Settings(), seconds_per_solve=5)
    assert result.status == "optimized"
    assert not result.design.failed
    # Cargo is maximized: the hull keeps only what it needs to move (one Engine), the rest is Cargo Pods.
    assert result.design.outfits.get("Cargo Pod", 0) == 9
    assert result.design.metrics["cargo space"] == 140


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
