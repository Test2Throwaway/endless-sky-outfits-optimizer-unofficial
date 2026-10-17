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
outfitter "Shop"
	"Sold Gun"
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
