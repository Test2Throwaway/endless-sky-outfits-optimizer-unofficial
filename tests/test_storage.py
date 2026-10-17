import os
from pathlib import Path

import pytest

from es_optimizer import calculator, gamedata
from es_optimizer.cli import main
from es_optimizer.storage import NoCatalog, Settings, Store

GAME = '''
outfit "Gun"
	category "Guns"
	mass 5
	"outfit space" -10
	"gun ports" -1
	weapon
		reload 10
		"shield damage" 20
		"damage dropoff" 0 500
		stream
	description "A gun."

outfit "Old Thing"
	category "Systems"
	"outfit space" -1

ship "Boat"
	attributes
		category "Light Warship"
		mass 100
		drag 2
		"outfit space" 50
		"heat dissipation" .5
	gun 0 0 "Gun"
	outfits
		"Gun"
'''


@pytest.fixture
def game_dir(tmp_path: Path) -> Path:
    (tmp_path / "game" / "data" / "_deprecated").mkdir(parents=True)
    (tmp_path / "game" / "data" / "test.txt").write_text(GAME)
    (tmp_path / "game" / "data" / "_deprecated" / "old.txt").write_text('outfit "Older"\n\tcategory "Systems"\n')
    return tmp_path / "game"


def test_no_catalog_until_import(tmp_path):
    with pytest.raises(NoCatalog):
        Store(tmp_path / "home").load_catalog()
    assert main(["--home", str(tmp_path / "home"), "summary"]) == 1


def test_catalog_round_trip(tmp_path, game_dir):
    parsed = gamedata.load(game_dir)
    store = Store(tmp_path / "home")
    store.save_catalog(parsed, [str(game_dir)])
    loaded = store.load_catalog()
    assert loaded.outfits["Gun"] == parsed.outfits["Gun"]
    assert loaded.outfits["Gun"].weapon.flags == {"stream"}
    assert loaded.outfits["Gun"].weapon.damage_dropoff == (0, 500)
    assert loaded.hulls["Boat"].attributes == parsed.hulls["Boat"].attributes
    assert loaded.hulls["Boat"].stock_outfits == {"Gun": 1}


def test_import_reports_changes(tmp_path, game_dir, capsys):
    home = ["--home", str(tmp_path / "home")]
    assert main([*home, "import", str(game_dir)]) == 0
    assert "es-optimizer setup" in capsys.readouterr().out
    assert main([*home, "import", str(game_dir)]) == 0
    assert "No changes" in capsys.readouterr().out
    (game_dir / "data" / "more.txt").write_text('outfit "New Gun"\n\tcategory "Guns"\n')
    assert main([*home, "import", str(game_dir)]) == 0
    assert "New outfits: New Gun" in capsys.readouterr().out


def test_blocklist_persists(tmp_path, game_dir, capsys):
    home = ["--home", str(tmp_path / "home")]
    main([*home, "import", str(game_dir)])
    assert main([*home, "block", "--outfit", "Gun", "--category", "Systems"]) == 0
    settings = Store(tmp_path / "home").load_settings()
    assert settings.blocked_outfits == {"Gun"} and settings.blocked_categories == {"Systems"}
    assert main([*home, "block", "--outfit", "No Such Thing"]) == 1
    assert main([*home, "unblock", "--outfit", "Gun"]) == 0
    assert Store(tmp_path / "home").load_settings().blocked_outfits == set()


def test_availability_rules(game_dir):
    game = gamedata.load(game_dir)
    settings = Settings()
    assert settings.outfit_available(game.outfits["Gun"])
    assert not settings.outfit_available(game.outfits["Older"])  # deprecated: blocked by default
    settings.allow_deprecated = True
    assert settings.outfit_available(game.outfits["Older"])
    settings.blocked_categories.add("Guns")
    assert not settings.outfit_available(game.outfits["Gun"])


@pytest.mark.skipif(not os.environ.get("ES_DATA"), reason="set ES_DATA to an Endless Sky checkout")
def test_real_catalog_gives_identical_results(tmp_path):
    parsed = gamedata.load(Path(os.environ["ES_DATA"]))
    store = Store(tmp_path / "home")
    store.save_catalog(parsed, [os.environ["ES_DATA"]])
    loaded = store.load_catalog()
    for name, hull in list(parsed.hulls.items()) + list(parsed.variants.items()):
        a = calculator.build(parsed, hull, hull.stock_outfits)
        b = calculator.build(loaded, loaded.hulls.get(name) or loaded.variants[name], hull.stock_outfits)
        assert (a.attributes, a.mass, a.fit_errors) == (b.attributes, b.mass, b.fit_errors), name
        assert [w.shield_damage for w in a.weapons] == [w.shield_damage for w in b.weapons], name


def test_license_block(tmp_path, game_dir):
    (game_dir / "data" / "lic.txt").write_text(
        'outfit "Torch"\n\tcategory "Engines"\n\tlicenses\n\t\t"Avgi Torch"\n')
    home = ["--home", str(tmp_path / "home")]
    main([*home, "import", str(game_dir)])
    assert main([*home, "block", "--license", "Avgi Torch"]) == 0
    assert main([*home, "block", "--license", "Nope"]) == 1
    store = Store(tmp_path / "home")
    settings, game = store.load_settings(), store.load_catalog()
    assert settings.missing_licenses(game.outfits["Torch"]) == ["Avgi Torch"]
    assert settings.missing_licenses(game.outfits["Gun"]) == []


def test_hull_search_and_suggestions(tmp_path, game_dir, capsys):
    home = ["--home", str(tmp_path / "home")]
    main([*home, "import", str(game_dir)])
    capsys.readouterr()
    assert main([*home, "hulls", "--all", "--variants"]) == 0
    listed = capsys.readouterr().out
    assert "hull(s)" in listed
    assert main([*home, "show", "hull", "definitely not a hull"]) == 1
    assert "No hull named" in capsys.readouterr().err
