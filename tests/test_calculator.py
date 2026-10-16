import math
import os
from pathlib import Path

import pytest

from es_optimizer import calculator, gamedata

FIXTURE = '''
ship "Boat"
	attributes
		category "Light Warship"
		cost 1000
		mass 100
		drag 2
		"heat dissipation" .5
		"outfit space" 100
		"weapon capacity" 30
		"engine capacity" 30
		shields 1000
		hull 500
		"fuel capacity" 300
	gun 0 0
	turret 0 0

outfit "Engine"
	category "Engines"
	mass 10
	"outfit space" -20
	"engine capacity" -20
	thrust 10
	"thrusting energy" 1
	"thrusting heat" 2
	turn 300
	"turning energy" .5
	"turning heat" 1

outfit "Reactor"
	category "Power"
	mass 20
	"outfit space" -20
	"energy generation" 3
	"heat generation" 4

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
		"firing heat" 8
		"shield damage" 20
		"hull damage" 10

outfit "Big Gun"
	category "Guns"
	"outfit space" -40
	"weapon capacity" -40
	"gun ports" -1

outfit "Limiter"
	category "Systems"
	"outfit space" -1
	"shield protection" -0.5

outfit "Expansion"
	category "Systems"
	"outfit space" 15
	"cooling inefficiency" 1
'''


@pytest.fixture
def game(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "test.txt").write_text(FIXTURE)
    return gamedata.load(tmp_path)


def test_totals_and_movement(game):
    ship = calculator.build(game, game.hulls["Boat"], {"Engine": 1, "Reactor": 1, "Gun": 1})
    assert ship.fit_errors == []
    assert ship.mass == 100 + 10 + 20 + 5
    assert ship.get("outfit space") == 100 - 20 - 20 - 10
    assert ship.max_speed == pytest.approx(60 * 10 / 2)
    assert ship.acceleration == pytest.approx(3600 * 10 / 135)
    assert ship.turn_rate == pytest.approx(60 * 300 / 135)


def test_fit_rule(game):
    too_big = calculator.build(game, game.hulls["Boat"], {"Big Gun": 1})
    assert any(e.startswith("weapon capacity") for e in too_big.fit_errors)
    too_many = calculator.build(game, game.hulls["Boat"], {"Gun": 2})
    assert any(e.startswith("gun ports") for e in too_many.fit_errors)
    # Shield protection may go down to -0.99, but not below.
    assert calculator.build(game, game.hulls["Boat"], {"Limiter": 1}).fit_errors == []
    assert calculator.build(game, game.hulls["Boat"], {"Limiter": 2}).fit_errors != []


def test_weapon_rates(game):
    ship = calculator.build(game, game.hulls["Boat"], {"Gun": 1})
    [gun] = ship.weapons
    assert gun.range == 600
    assert gun.shield_damage == pytest.approx(2.0)   # 20 per shot, one shot per 10 frames
    assert gun.energy == pytest.approx(0.5)
    assert not gun.turret


def test_heat(game):
    ship = calculator.build(game, game.hulls["Boat"], {"Reactor": 1})
    assert ship.max_heat == 100 * 120
    # Settles where heat × 0.001 × dissipation equals heat produced.
    assert ship.equilibrium_heat(4) == pytest.approx(4 / (0.001 * 0.5))


def test_cooling_efficiency_curve(game):
    effs = [calculator.build(game, game.hulls["Boat"], {"Expansion": n}).cooling_efficiency for n in (0, 2, 4)]
    assert effs[0] == 1.0
    assert effs[1] == pytest.approx(0.972, abs=1e-3)
    assert effs[2] == pytest.approx(0.837, abs=1e-3)


def test_comfortable_range():
    assert calculator.comfortable_range(30) == 900
    assert calculator.comfortable_range(95) == pytest.approx(500)
    assert calculator.comfortable_range(200) == 0


@pytest.mark.skipif(not os.environ.get("ES_DATA"), reason="set ES_DATA to an Endless Sky checkout")
def test_stock_argosy_matches_game_display():
    game = gamedata.load(Path(os.environ["ES_DATA"]))
    hull = game.variants["Argosy (Laser)"]
    ship = calculator.build(game, hull, hull.stock_outfits)
    assert ship.fit_errors == []
    assert round(ship.max_speed) == 315
    assert round(ship.acceleration) == 177
    assert round(ship.turn_rate) == 129
    assert math.isclose(ship.average_jump_fuel, 100)
