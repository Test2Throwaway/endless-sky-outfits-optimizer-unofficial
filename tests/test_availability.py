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
outfitter "Shop"
	"Sold Gun"
''',
    "human/ships.txt": '''
ship "Raider"
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
''',
    "quarg/ships.txt": '''
outfit "Quarg Gun"
	category "Guns"
ship "Quarg Ship"
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
    assert reason("Story Thing") is None                    # no source: story rewards stay available
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
