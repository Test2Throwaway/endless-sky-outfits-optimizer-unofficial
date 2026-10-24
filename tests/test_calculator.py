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


CAPTURE = '''
outfit "Beam"
	category "Guns"
	"gun ports" -1
	weapon
		lifetime 1
		velocity 300
		"shield damage" 1
		"hull damage" 3

outfit "Disruptor"
	category "Turrets"
	"turret mounts" -1
	weapon
		lifetime 1
		velocity 300
		"disruption damage" 1
'''


def test_capture_intact(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "test.txt").write_text(FIXTURE + CAPTURE)
    game = gamedata.load(tmp_path)
    role = calculator.Role(goal="capture-intact", needs_drives=False, needs_ramscoop=False,
                           needs_anti_missile=False)
    slow = calculator.build(game, game.hulls["Boat"], {"Gun": 1})
    assert not slow.weapons[0].instantaneous
    assert slow.weapon_value(slow.weapons[0], "capture-intact") == 0
    checks = {c.name: c.passed for c in calculator.evaluate(slow, role)}
    assert checks["Capture-intact: instantaneous weapons only"] is False

    beam = calculator.build(game, game.hulls["Boat"], {"Beam": 1, "Engine": 1})
    assert beam.weapons[0].instantaneous
    target = calculator.build(game, game.hulls["Boat"], {})   # shields 1000, hull 500
    # Disable threshold (Ship::FinishLoading): 500 × (0.1 × 0.2 + 0.5 × 0.8) = 210.
    assert target.disable_threshold == 210
    checks = {c.name: c.passed for c in calculator.evaluate(beam, role, True, [target])}
    assert checks["Capture-intact: instantaneous weapons only"] is True
    # Without disruption no hull damage gets through the shields, so the target can't be disabled intact.
    assert checks["Capture-intact: disabled with shields ≥ 50%"] is False
    both = calculator.build(game, game.hulls["Boat"], {"Beam": 1, "Disruptor": 1, "Engine": 1})
    result = calculator.capture_intact(both, target)
    # Disruption 1 per frame holds the level at 99, so about half of each hit reaches the hull.
    assert result.passed and result.shields_left == pytest.approx(0.871, abs=0.01)
    # With disruption available, instantaneous weapons are scored with the destroy weights.
    w = beam.weapons[0]
    assert beam.weapon_value(w, "capture-intact", True) > beam.weapon_value(w, "capture-intact", False)


HULL_TYPES = '''
ship "Dart"
	attributes
		category "Interceptor"
		mass 50
		drag 1
		"heat dissipation" .8
		"outfit space" 100
		"weapon capacity" 30
		"energy capacity" 1000
	gun 0 0

ship "Wasp"
	attributes
		category "Fighter"
		mass 20
		drag 1
		"heat dissipation" .8
		"outfit space" 50
		"weapon capacity" 30
	gun 0 0
'''


def test_hull_type_exceptions(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "test.txt").write_text(FIXTURE + HULL_TYPES)
    game = gamedata.load(tmp_path)
    role = calculator.Role()
    names = lambda hull: {c.name: c for c in calculator.evaluate(
        calculator.build(game, game.hulls[hull], {"Engine": 1, "Reactor": 1, "Gun": 1}), role)}

    interceptor = names("Dart")
    assert "Anti-missile" not in interceptor and "Ramscoop (rule 1)" not in interceptor
    assert "jump drive" not in interceptor["Drives"].detail          # only hyperdrive and keystone wanted
    assert "Weapons in combat: energy" not in interceptor
    assert "Interceptor reserves: energy for a 90 s battle" in interceptor

    fighter = names("Wasp")
    assert not {"Drives", "Ramscoop (rule 1)", "Anti-missile"} & set(fighter)
    assert "Burst: all weapons 2.5 s" in fighter                      # fighters use the non-combat weapon rules

    boat = names("Boat")
    assert {"Drives", "Ramscoop (rule 1)", "Anti-missile", "Combat (240 s): energy", "Cruising: energy"} <= set(boat)


def test_heat_after_approaches_equilibrium(game):
    ship = calculator.build(game, game.hulls["Boat"], {"Reactor": 1})
    target = ship.equilibrium_heat(4)
    assert ship.heat_after(4, 0) == 0
    assert 0 < ship.heat_after(4, 1000) < target
    assert ship.heat_after(4, 1e6) == pytest.approx(target)


MAGAZINE = '''
outfit "Launcher"
	category "Secondary Weapons"
	"gun ports" -1
	"rocket capacity" 10
	weapon
		ammo "Rocket"
		reload 60
		velocity 20
		lifetime 100
		"hull damage" 100

outfit "Rocket"
	category "Ammunition"
	"rocket capacity" -1

outfit "Rocket Rack"
	category "Ammunition"
	"outfit space" -5
	"rocket capacity" 30
'''


def test_magazine_depth_and_window(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "test.txt").write_text(FIXTURE + MAGAZINE)
    game = gamedata.load(tmp_path)
    role = calculator.Role(fight_seconds=90.0, needs_drives=False, needs_ramscoop=False, needs_anti_missile=False)
    # Range 2000: long range, used for the first 50% of a 90 s fight: 45 shots per fight, 90 for two fights.
    short = calculator.build(game, game.hulls["Boat"], {"Launcher": 1, "Rocket": 10, "Engine": 1})
    [w] = short.weapons
    assert w.range == 2000 and calculator.magazine_window(w, 90.0) == 0.5
    check = {c.name: c for c in calculator.evaluate(short, role)}["Magazine: Rocket"]
    assert check.passed is False and "needs 90" in check.detail
    deep = calculator.build(game, game.hulls["Boat"], {"Launcher": 1, "Rocket Rack": 3, "Rocket": 90, "Engine": 1})
    assert deep.fit_errors == []
    assert {c.name: c for c in calculator.evaluate(deep, role)}["Magazine: Rocket"].passed
    # Its damage counts for half the fight.
    full = w.hull_damage * 0.4   # normal goal: hull weight 0.4
    assert short.weapon_value(w, "normal", fight_seconds=90.0) < full


def test_combat_fire_rate_factor():
    from types import SimpleNamespace
    slow = SimpleNamespace(shots_per_second=2.0)
    assert calculator.fire_rate_factor(slow) == pytest.approx((2 / 6) ** calculator.COMBAT_RATE_EXPONENT)
    assert calculator.fire_rate_factor(SimpleNamespace(shots_per_second=4 / 3)) == pytest.approx(0.2, abs=0.005)
    assert calculator.fire_rate_factor(SimpleNamespace(shots_per_second=6.0)) == 1.0
    assert calculator.fire_rate_factor(SimpleNamespace(shots_per_second=60.0)) == 1.0


def test_turret_turn_and_projectile_speed_factors():
    from types import SimpleNamespace as W
    slow_turret = W(turret=True, homing=False, turret_turn=75.0)
    assert calculator.turret_turn_factor(slow_turret) == pytest.approx(0.5)
    assert calculator.turret_turn_factor(W(turret=True, homing=True, turret_turn=0.0)) == 1.0   # homing: exempt
    assert calculator.turret_turn_factor(W(turret=False, homing=False, turret_turn=0.0)) == 1.0  # guns: exempt
    assert calculator.projectile_speed_factor(W(instantaneous=False, projectile_speed=300.0)) == pytest.approx(0.5)
    assert calculator.projectile_speed_factor(W(instantaneous=True, projectile_speed=0.0)) == 1.0  # beams
    assert calculator.projectile_speed_factor(W(instantaneous=False, projectile_speed=6000.0)) == 1.0


def test_thrust_made_energy_counts_less_on_slow_ships():
    from types import SimpleNamespace as S
    nimble, tank = calculator.thrust_shares(S(agility=150.0)), calculator.thrust_shares(S(agility=55.0))
    assert nimble == (calculator.TORCH_THRUST_SHARE, calculator.TORCH_THRUST_SHARE)
    assert tank[1] == pytest.approx(calculator.TORCH_THRUST_SHARE * 0.5)


def test_projectile_speed_uses_submunition_and_top_speed():
    from es_optimizer.gamedata import Weapon
    from types import SimpleNamespace
    sub = Weapon(stats={"velocity": 10.0}, flags=set(), ammo=None, submunitions=[], damage_dropoff=None)
    game = SimpleNamespace(outfits={"Sub": SimpleNamespace(weapon=sub)})
    parent = Weapon(stats={"lifetime": 1.0}, flags=set(), ammo=None, submunitions=[("Sub", 1)], damage_dropoff=None)
    assert calculator.projectile_speed(game, parent) == 10.0
    missile = Weapon(stats={"velocity": 2.0, "acceleration": 1.0, "drag": 0.1}, flags=set(), ammo=None,
                     submunitions=[], damage_dropoff=None)
    assert calculator.projectile_speed(game, missile) == pytest.approx(10.0)


def test_weapon_value_is_relative_to_the_average_weapon():
    from types import SimpleNamespace as W
    good = W(range=1000.0, turret=True, homing=False, turret_turn=300.0, instantaneous=True, shots_per_second=60.0,
             projectile_speed=0.0, ammo=None, shield_damage=1.0, hull_damage=1.0)
    poor = W(**{**good.__dict__, "range": 100.0})           # far below the comfortable range of a slow ship
    agility = 60.0
    assert calculator.suitability(good, agility) == 1.0
    average = calculator.average_suitability((good, poor), agility, 240.0, False, "normal")
    assert average == pytest.approx((1.0 + calculator.suitability(poor, agility)) / 2)
    ship = calculator.Ship(hull=None, outfits={}, attributes={"thrust": 1, "turn": 1}, mass=1.0, cost=0, fit_errors=[],
                           weapons=[])
    ship_agility = ship.agility
    plain = ship.weapon_value(good)
    relative = ship.weapon_value(good, reference=(good, poor))
    avg = calculator.average_suitability((good, poor), round(ship_agility, 1), 240.0, False, "normal")
    assert relative == pytest.approx(plain / avg)            # the average weapon counts its full damage


def test_dropoff_factor_averages_over_engagement_distance():
    from types import SimpleNamespace as W
    w = W(dropoff=(100.0, 300.0), dropoff_modifier=0.5)
    assert calculator.dropoff_factor(w, 100.0) == 1.0
    # 0-100 at 1, 100-300 falling to 0.5 (average 0.75), 300-400 at 0.5.
    assert calculator.dropoff_factor(w, 400.0) == pytest.approx((100 + 200 * 0.75 + 100 * 0.5) / 400)
    assert calculator.dropoff_factor(W(dropoff=None, dropoff_modifier=1.0), 500.0) == 1.0


def test_homing_block_turret_turn_default_and_delays(tmp_path):
    text = FIXTURE + '''
outfit "Seeker"
	category "Secondary Weapons"
	"outfit space" -5
	"weapon capacity" -5
	"gun ports" -1
	weapon
		homing
			leading
		velocity 10
		lifetime 50
		reload 30
		"hull damage" 10

outfit "Old Turret"
	category "Turrets"
	"outfit space" -5
	"weapon capacity" -5
	"turret mounts" -1
	weapon
		velocity 10
		lifetime 50
		reload 10
		"hull damage" 10

outfit "Slow Shields"
	category "Systems"
	"shield generation" 1
	"shield delay" 30
	"depleted shield delay" 120
'''
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "t.txt").write_text(text)
    game = gamedata.load(tmp_path)
    seeker = calculator._weapon_stats(game, game.outfits["Seeker"], 1)
    assert seeker.homing
    turret = calculator._weapon_stats(game, game.outfits["Old Turret"], 1)
    assert turret.turret_turn == pytest.approx(calculator.LEGACY_TURRET_TURN * calculator.FPS)
    ship = calculator.build(game, game.hulls["Boat"], {"Slow Shields": 1})
    shields, _ = calculator.regen_times(ship)
    assert shields == pytest.approx(1000 / 1 + 120)
