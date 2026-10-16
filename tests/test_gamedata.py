import os
from pathlib import Path

import pytest

from es_optimizer import gamedata

FIXTURE = '''
outfit "Blaster"
	category "Guns"
	cost 10000
	mass 5
	"outfit space" -5
	"gun ports" -1
	weapon
		ammo "Cell" 2
		submunition "Spark" 3
		stream
		"reload" 10
		"shield damage" 4
		"damage dropoff" 100 1500
	description "First line."
	description "Second line."

outfit "Hyperdrive"
	category "Systems"
	"outfit space" -20
	"hyperdrive" 1

outfit "Jumper"
	"jump drive" 1
	"jump fuel" 150

outfit "Blaster"
	cost 12000

ship "Boat"
	attributes
		category "Light Warship"
		cost 100000
		mass 50
		"outfit space" 100
		licenses
			Navy
	outfits
		"Blaster" 2
		Hyperdrive
	gun 1 2 "Blaster"
	gun 3 4 "Blaster"
	turret 0 0
	bay "Fighter" 0 0 over
	fighter 1 1

ship "Boat" "Boat (Plain)"
	outfits
		Hyperdrive

ship "Boat" "Boat (Armored)"
	add attributes
		"outfit space" 10
		hull 500

ship "Boat" "Boat (Refit)"
	attributes
		category "Utility"
		"outfit space" 40
	gun "Blaster"

overwrite
outfit "Hyperdrive"
	category "Systems"

outfitter "Shop"
	"Blaster"
	Hyperdrive
	remove "Blaster"
	add Jumper

outfitter "Shop"
	stock
		Blaster
'''


@pytest.fixture
def game(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "test.txt").write_text(FIXTURE)
    return gamedata.load(tmp_path)


def test_outfit_fields(game):
    blaster = game.outfits["Blaster"]
    assert blaster.category == "Guns"
    assert blaster.cost == 12000  # A second definition merges into the first.
    assert blaster.mass == 5
    assert blaster.attributes == {"outfit space": -5, "gun ports": -1}
    assert blaster.description == ["First line.", "Second line."]
    assert blaster.source == "data/test.txt:2"
    weapon = blaster.weapon
    assert weapon.ammo == ("Cell", 2)
    assert weapon.submunitions == [("Spark", 3)]
    assert weapon.flags == {"stream"}
    assert weapon.stats == {"reload": 10, "shield damage": 4}
    assert weapon.damage_dropoff == (100, 1500)


def test_overwrite_and_jump_defaults(game):
    # "overwrite" clears the earlier Hyperdrive definition entirely.
    assert game.outfits["Hyperdrive"].attributes == {}
    assert game.outfits["Jumper"].attributes == {"jump drive": 1, "jump drive fuel": 150}


def test_hull_model(game):
    boat = game.hulls["Boat"]
    assert boat.variant is None
    assert boat.category == "Light Warship"
    assert boat.cost == 100000 and boat.mass == 50
    assert boat.licenses == ["Navy"]
    assert boat.gun_ports == 2 and boat.turret_mounts == 1
    assert boat.attributes["gun ports"] == 2 and boat.attributes["turret mounts"] == 1
    assert boat.bays == {"Fighter": 2}
    assert boat.stock_outfits == {"Blaster": 2, "Hyperdrive": 1}


def test_variants_inherit(game):
    plain = game.variants["Boat (Plain)"]
    assert plain.model == "Boat"
    assert plain.attributes == game.hulls["Boat"].attributes
    assert plain.stock_outfits == {"Hyperdrive": 1}
    assert plain.gun_ports == 2 and plain.bays == {"Fighter": 2}

    armored = game.variants["Boat (Armored)"]
    assert armored.attributes["outfit space"] == 110
    assert armored.attributes["hull"] == 500
    assert armored.stock_outfits == {"Blaster": 2, "Hyperdrive": 1}
    # Adding to a variant must not change the model.
    assert game.hulls["Boat"].attributes["outfit space"] == 100

    refit = game.variants["Boat (Refit)"]
    assert refit.category == "Utility"
    assert refit.attributes["outfit space"] == 40
    # Hardpoints without positions keep the model's hardpoints.
    assert refit.gun_ports == 2 and refit.turret_mounts == 1


def test_shop(game):
    # A second definition with a plain "stock" node replaces the stock.
    assert game.outfitters["Shop"].items == ["Blaster"]


@pytest.mark.skipif(not os.environ.get("ES_DATA"), reason="set ES_DATA to an Endless Sky checkout")
def test_real_data_stock_ships_fit():
    game = gamedata.load(Path(os.environ["ES_DATA"]))
    assert not game.warnings
    assert len(game.outfits) > 500 and len(game.hulls) > 200
    capacities = ["outfit space", "weapon capacity", "engine capacity", "gun ports", "turret mounts"]
    over = []
    for hull in list(game.hulls.values()) + list(game.variants.values()):
        for key in capacities:
            total = hull.attributes.get(key, 0) + sum(
                game.outfits[name].attributes.get(key, 0) * count
                for name, count in hull.stock_outfits.items())
            if total < -1e-9:
                over.append(hull.name)
                break
    # Only scripted Remnant wrecks are deliberately over capacity.
    assert all("Dromedary" in name for name in over), over
