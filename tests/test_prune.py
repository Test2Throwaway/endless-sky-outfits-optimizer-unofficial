from pathlib import Path

import pytest

from es_optimizer import gamedata, roles, solver
from es_optimizer.availability import Availability
from es_optimizer.prune import prune_obsolete
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
	turret 0 0

outfit "Good Thruster"
	category "Engines"
	cost 90000
	mass 10
	"outfit space" -10
	"engine capacity" -10
	thrust 6
	"thrusting energy" 1
	"thrusting heat" 1

outfit "Bad Thruster"
	category "Engines"
	cost 1000
	mass 10
	"outfit space" -10
	"engine capacity" -10
	thrust 5
	"thrusting energy" 1
	"thrusting heat" 1

outfit "Small Thruster"
	category "Engines"
	mass 5
	"outfit space" -5
	"engine capacity" -5
	thrust 2.8
	"thrusting energy" .5
	"thrusting heat" .5

outfit "Burner"
	category "Engines"
	mass 10
	"outfit space" -10
	"engine capacity" -10
	thrust 6
	"thrusting energy" 1
	"thrusting heat" 1
	"afterburner thrust" 5

outfit "Odd Thruster"
	category "Engines"
	mass 10
	"outfit space" -10
	"engine capacity" -10
	thrust 5
	"thrusting energy" 1
	"thrusting heat" 1
	"slowing protection" .1
	"mystery stat" 1

outfit "Brig"
	category "Systems"
	mass 3
	"outfit space" -3

outfit "Scanner"
	category "Systems"
	mass 1
	"outfit space" -1
	"cargo scan power" 9

outfit "Laser Turret"
	category "Turrets"
	mass 10
	"outfit space" -10
	"weapon capacity" -10
	"turret mounts" -1
	weapon
		reload 10
		velocity 20
		lifetime 30
		"hull damage" 10
		"shield damage" 10

outfit "Stiff Turret"
	category "Turrets"
	mass 10
	"outfit space" -10
	"weapon capacity" -10
	"turret mounts" -1
	weapon
		reload 10
		velocity 20
		lifetime 30
		"turret turn" 2
		"hull damage" 10
		"shield damage" 10

outfit "Ion Turret"
	category "Turrets"
	mass 10
	"outfit space" -10
	"weapon capacity" -10
	"turret mounts" -1
	weapon
		reload 10
		velocity 20
		lifetime 30
		"hull damage" 5
		"shield damage" 5
		"ion damage" 5

outfitter "Shop"
	"Good Thruster"
	"Bad Thruster"
	"Small Thruster"
	"Burner"
	"Odd Thruster"
	"Brig"
	"Scanner"
	"Laser Turret"
	"Stiff Turret"
	"Ion Turret"
'''


@pytest.fixture
def game(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "test.txt").write_text(GAME)
    return gamedata.load(tmp_path)


def prune(game, settings=None):
    settings = settings or Settings()
    return prune_obsolete(list(game.outfits.values()), Availability(game, settings))


def test_drops_only_what_another_outfit_beats_in_every_way(game):
    kept, dropped = prune(game)
    assert set(dropped) == {"Bad Thruster", "Stiff Turret"}
    assert dropped["Bad Thruster"] == "beaten by 2 × Small Thruster, Good Thruster"   # cost doesn't count
    assert dropped["Stiff Turret"] == "beaten by Laser Turret"   # no turret turn on a turret means 240°/s
    assert {o.name for o in kept} == set(game.outfits) - set(dropped)


def test_classes_unknown_stats_and_identity_outfits_are_kept(game):
    _, dropped = prune(game)
    assert "Burner" not in dropped          # afterburners are a class a role can forbid
    assert "Odd Thruster" not in dropped    # an unclassified stat never loses
    assert "Ion Turret" not in dropped      # effect damage is a class
    assert "Brig" not in dropped            # nothing but a footprint: its value is its name


def test_explicitly_allowed_outfits_are_kept(game):
    _, dropped = prune(game, Settings(allowed_outfits={"Bad Thruster"}))
    assert "Bad Thruster" not in dropped


def test_candidates_prune_only_when_asked(game):
    request = roles.combine([roles.parse_role('[should]\n"cargo space" = 1', "test")], {})
    hull = game.hulls["Boat"]
    assert "Bad Thruster" in {o.name for o in solver.candidates(game, hull, Settings(), request)}
    pruned: dict[str, str] = {}
    pool = solver.candidates(game, hull, Settings(), request, pruned)
    assert "Bad Thruster" not in {o.name for o in pool}
    assert "Bad Thruster" in pruned
