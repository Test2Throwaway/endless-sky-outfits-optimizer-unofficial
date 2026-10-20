from pathlib import Path

import pytest

from es_optimizer import calculator, gamedata, roles, solver
from es_optimizer.availability import Availability
from es_optimizer.prune_passes import prune_passes, solar_case
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
		shields 1000
		hull 500
	gun 0 0

outfit "Old Steering"
	category "Engines"
	mass 12
	"outfit space" -12
	"engine capacity" -12
	turn 288
	"turning energy" .3
	"turning heat" .6

outfit "New Steering"
	category "Engines"
	mass 8
	"outfit space" -8
	"engine capacity" -8
	turn 420
	"turning energy" .7
	"turning heat" 2.1

outfit "Hungry Steering"
	category "Engines"
	mass 10
	"outfit space" -10
	"engine capacity" -10
	turn 420
	"turning energy" 1.5
	"turning heat" 2.1

outfit "Old Shield"
	category "Systems"
	mass 15
	"outfit space" -15
	"shield generation" .2
	"shield energy" .2

outfit "Shield Core"
	category "Systems"
	mass 15
	"outfit space" -15
	"shield generation" .2
	"shield energy" .2
	"energy capacity" 1000

outfit "New Shield"
	category "Systems"
	mass 11
	"outfit space" -11
	"shield generation" .28
	"shield energy" .28

outfit "Weak Gun"
	category "Guns"
	mass 10
	"outfit space" -10
	"weapon capacity" -10
	"gun ports" -1
	weapon
		reload 10
		velocity 20
		lifetime 30
		"firing energy" 5
		"hull damage" 10
		"shield damage" 10
		"hit force" -40
		homing
			leading

outfit "Strong Gun"
	category "Guns"
	mass 10
	"outfit space" -10
	"weapon capacity" -10
	"gun ports" -1
	weapon
		reload 10
		velocity 20
		lifetime 30
		"firing energy" 4
		"hull damage" 12
		"shield damage" 12
		homing

outfitter "Shop"
	"Old Steering"
	"New Steering"
	"Hungry Steering"
	"Old Shield"
	"Shield Core"
	"New Shield"
	"Weak Gun"
	"Strong Gun"
'''


@pytest.fixture
def game(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "test.txt").write_text(GAME)
    return gamedata.load(tmp_path)


def run(game, should='"cargo space" = 1'):
    request = roles.combine([roles.parse_role(f"[should]\n{should}", "test")], {})
    return prune_passes(game, list(game.outfits.values()), Availability(game, Settings()), request)[1]


def test_engines_trade_power_for_space_at_both_duty_ends(game):
    dropped = run(game)
    # Against Old: 4 space saved pays for the extra power even at 100% turn duty; Hungry's 2 space saved doesn't.
    assert dropped["Old Steering"] == "beaten by New Steering (engines, normal)"
    assert dropped["Hungry Steering"] == "beaten by New Steering (engines, normal)"


def test_regeneration_keeps_outfits_with_other_stats(game):
    dropped = run(game)
    # A core with storage beats the plain shield it matches, but nothing without storage beats the core.
    assert dropped["Old Shield"] == "beaten by New Shield, Shield Core (regeneration, normal)"
    assert "Shield Core" not in dropped


def test_damage_lens_ignores_hit_force_unless_the_request_scores_it(game):
    assert run(game)["Weak Gun"] == "beaten by Strong Gun (damage lens)"
    assert "Weak Gun" not in run(game, should='"pull force" = 1')


def test_homing_with_a_block_is_a_flag(game):
    assert "homing" in game.outfits["Weak Gun"].weapon.flags


def test_solar_case_follows_the_role():
    assert solar_case(calculator.Role(must_run_dark=True)) == "dark"
    assert solar_case(calculator.Role(evader=True)) == "evader"
    assert solar_case(calculator.Role()) == "normal"


def test_candidates_run_the_passes(game):
    request = roles.combine([roles.parse_role('[should]\n"cargo space" = 1', "test")], {})
    pruned: dict[str, str] = {}
    pool = {o.name for o in solver.candidates(game, game.hulls["Boat"], Settings(), request, pruned)}
    assert "Old Steering" not in pool and "Old Steering" in pruned
