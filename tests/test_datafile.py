from es_optimizer.datafile import is_number, parse_text, to_number


def test_tokens_and_nesting():
    nodes = parse_text(
        'outfit "Heavy Laser"\n'
        '\tcategory "Guns"\n'
        '\t# a comment\n'
        '\n'
        '\t"outfit space" -15 # trailing comment\n'
        '\tweapon\n'
        '\t\t`shield damage` 1.7\n'
        'ship Argosy\n')
    assert [n.tokens for n in nodes] == [["outfit", "Heavy Laser"], ["ship", "Argosy"]]
    outfit = nodes[0]
    assert [c.tokens for c in outfit] == [
        ["category", "Guns"], ["outfit space", "-15"], ["weapon"]]
    assert outfit.children[2].children[0].tokens == ["shield damage", "1.7"]
    assert outfit.children[1].line == 5


def test_dedent_to_middle_level():
    nodes = parse_text("a\n\tb\n\t\tc\n\td\ne\n")
    assert [n.key for n in nodes] == ["a", "e"]
    assert [c.key for c in nodes[0]] == ["b", "d"]
    assert nodes[0].children[0].children[0].key == "c"


def test_quote_edge_cases():
    [node] = parse_text('key "has # hash" "" `"quoted"` "unterminated\n')
    assert node.tokens == ["key", "has # hash", "", '"quoted"', "unterminated"]


def test_bom_and_crlf():
    [node] = parse_text('﻿key 1\r\n')
    assert node.tokens == ["key", "1"]


def test_numbers_match_game_rules():
    assert to_number(".56") == 0.56
    assert to_number("1.") == 1.0
    assert to_number("-2.5e2") == -250.0
    assert to_number("+3") == 3.0
    assert to_number("4e") == 4.0
    assert to_number("abc") == 0.0
    assert to_number("-") == 0.0
    assert not is_number("1.2.3")
    assert not is_number("inf")
    assert not is_number("1e5e5")
