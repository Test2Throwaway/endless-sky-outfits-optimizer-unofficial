from pathlib import Path

import pytest

from es_optimizer import gamedata
from es_optimizer.availability import Availability
from es_optimizer.storage import Settings

GAME = {
    "human/outfits.txt": '''
outfit "Sold Gun"
	category "Guns"
outfit "Pirate Gun"
	category "Guns"
outfit "Locked"
	category "Systems"
	unplunderable 1
outfit "Hero Thing"
	category "Systems"
outfit "Story Thing"
	category "Systems"
outfit "Future Thing"
	category "Systems"
outfit "Event Thing"
	category "Systems"
outfit "Ghost Gun"
	category "Guns"
outfit "Navy Gun"
	category "Guns"
	licenses
		Navy
outfit "Navy Shield"
	category "Systems"
	licenses
		Navy
outfitter "Shop"
	"Sold Gun"
	"Navy Gun"
	"Navy Shield"
mission "Gift"
	on complete
		outfit "Story Thing"
event "New Stock"
	outfitter "Shop"
		"Event Thing"
''',
    "human/ships.txt": '''
ship "Raider"
	sprite "ship/raider"
	attributes
		category "Light Warship"
	outfits
		"Pirate Gun"
		Locked
		"Navy Gun"
ship "Raider" "Famous Raider"
	"never disabled"
	outfits
		"Hero Thing"
person "Captain"
	ship "Famous Raider"
ship "Ghost"
	attributes
		category "Light Warship"
	outfits
		"Ghost Gun"
ship "Museum Piece"
	sprite "ship/museum"
	attributes
		category "Light Warship"
	outfits
		"Museum Gun"
ship "Trader"
	sprite "ship/trader"
	attributes
		category "Light Freighter"
	outfits
		"Trade Gun"
outfit "Museum Gun"
	category "Guns"
outfit "Trade Gun"
	category "Guns"
government "Pirate"
government "Pirate (Hostile)"
	"display name" "Pirate"
government "Merchant"
fleet "Raiders"
	government "Pirate"
	variant 2
		"Raider"
		"Ghost"
fleet "Angry Raiders"
	government "Pirate (Hostile)"
	variant
		"Raider"
mission "Convoy"
	npc
		government "Merchant"
		ship "Trader" "Lucky Lady"
''',
    "quarg/ships.txt": '''
outfit "Quarg Gun"
	category "Guns"
ship "Quarg Ship"
	sprite "ship/quarg"
	attributes
		category "Heavy Warship"
	outfits
		"Quarg Gun"
government "Quarg"
fleet "Quarg Patrol"
	government "Quarg"
	variant
		"Quarg Ship"
''',
}


@pytest.fixture
def game(tmp_path: Path):
    for name, text in GAME.items():
        path = tmp_path / "data" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return gamedata.load(tmp_path)


def test_source_rules(game):
    a = Availability(game, Settings())
    reason = lambda n: a.outfit_reason(game.outfits[n])
    assert reason("Sold Gun") is None
    assert reason("Pirate Gun") is None                     # plunderable from a counted source
    assert reason("Locked") == "unplunderable and not sold anywhere"
    assert "can't be disabled" in reason("Hero Thing")      # only on a person ship
    assert reason("Story Thing") is None                    # mission item: available, one copy
    assert a.copy_limit(game.outfits["Story Thing"]) == 1
    assert reason("Future Thing") == "defined but used nowhere (future content)"
    assert reason("Event Thing") is None                    # shop stock added by an event counts as sold
    assert a.copy_limit(game.outfits["Event Thing"]) is None
    assert "can't be disabled" in reason("Ghost Gun")       # only on a ship with no sprite
    assert game.variants["Famous Raider"].has_sprite        # inherited from its model
    assert "blocked sources: quarg" in reason("Quarg Gun")  # Quarg blocked by default
    assert game.persons == {"Captain": ["Famous Raider"]}
    assert game.variants["Famous Raider"].never_disabled


def test_unblocking_a_source_and_explicit_allow(game):
    settings = Settings()
    settings.blocked_sources.discard("quarg")
    assert Availability(game, settings).outfit_ok(game.outfits["Quarg Gun"])
    settings = Settings(allowed_outfits={"Locked"})
    assert Availability(game, settings).outfit_ok(game.outfits["Locked"])
    settings = Settings(blocked_outfits={"Sold Gun"})
    assert not Availability(game, settings).outfit_ok(game.outfits["Sold Gun"])


def test_licence_blocks_buying_not_plundering(game):
    a = Availability(game, Settings(blocked_licenses={"Navy"}))
    assert a.outfit_reason(game.outfits["Navy Gun"]) is None             # plunderable from the Raider
    assert "licence" in a.outfit_reason(game.outfits["Navy Shield"])    # only sold, needs the licence
    assert Availability(game, Settings()).outfit_ok(game.outfits["Navy Shield"])
    raider_source_blocked = Settings(blocked_licenses={"Navy"}, blocked_sources={"human"})
    assert not Availability(game, raider_source_blocked).outfit_ok(game.outfits["Navy Gun"])


def test_licence_blocks_buying_not_capturing(game):
    raider = game.hulls["Raider"]
    raider.base.licenses.append("Navy")
    assert Availability(game, Settings(blocked_licenses={"Navy"})).hull_ok(raider)     # can be captured
    raider.uncapturable = True
    assert "captured" in Availability(game, Settings(blocked_licenses={"Navy"})).hull_reason(raider)


def test_flown_by_governments(game):
    assert game.government_ships["Pirate"] == ["Ghost", "Raider"]
    assert game.government_ships["Pirate (Hostile)"] == ["Raider"]
    assert game.government_ships["Merchant"] == ["Trader"]          # from a mission NPC
    assert game.government_names["Pirate (Hostile)"] == "Pirate"
    a = Availability(game, Settings())
    assert a.outfit_ok(game.outfits["Museum Gun"])         # flown by no government: no relations to damage
    assert Availability(game, Settings(blocked_governments={"Pirate", "Pirate (Hostile)", "Merchant"})).outfit_ok(
        game.outfits["Museum Gun"])
    assert a.outfit_ok(game.outfits["Trade Gun"])


def test_governments_you_wont_attack(game):
    # Each government is its own choice, whatever its display name.
    choices = {g: (only, shared) for g, only, shared in Availability(game, Settings()).government_choices()}
    # Pirate Gun is on a ship two governments fly; Quarg's source group is blocked.
    assert choices == {"Merchant": (1, 0), "Pirate": (0, 1), "Pirate (Hostile)": (0, 1)}
    a = Availability(game, Settings())
    assert not a.attacks("Pirate")                                   # it has a "(Hostile)" twin: spared
    assert a.outfit_ok(game.outfits["Pirate Gun"])                   # Pirate (Hostile) also flies the Raider
    both = Availability(game, Settings(blocked_governments={"Pirate", "Pirate (Hostile)"}))
    assert "won't attack: Pirate, Pirate (Hostile)" in both.outfit_reason(game.outfits["Pirate Gun"])


def test_default_attack_from_names():
    from es_optimizer.availability import default_attack
    names = {"Korath", "Korath (Civilian)", "Merchant", "Merchant (Hostile)", "Republic"}
    assert default_attack("Korath (Civilian)", names) is False      # at peace at the start: spared
    assert default_attack("Korath", names) is True                  # its civilian twin's opposite
    assert default_attack("Merchant (Hostile)", names) is True
    assert default_attack("Merchant", names) is False               # its hostile twin's opposite
    assert default_attack("Republic", names) is True


def test_government_choice_overrides_default(game):
    game.government_names["Pirate (Civilian)"] = "Pirate"
    game.government_ships["Pirate (Civilian)"] = ["Museum Piece"]
    a = Availability(game, Settings())
    assert not a.attacks("Pirate (Civilian)")
    assert not a.outfit_ok(game.outfits["Museum Gun"])               # only a civilian government flies it
    assert Availability(game, Settings(allowed_governments={"Pirate (Civilian)"})).outfit_ok(game.outfits["Museum Gun"])


def test_choices_ignore_outfits_on_ships_no_government_flies(game):
    assert "Merchant" in {g for g, _, _ in Availability(game, Settings()).government_choices()}
    game.hulls["Museum Piece"].stock_outfits["Trade Gun"] = 1      # also on a ship no government flies
    assert "Merchant" not in {g for g, _, _ in Availability(game, Settings()).government_choices()}
    assert Availability(game, Settings(blocked_governments={"Merchant"})).outfit_ok(game.outfits["Trade Gun"])
