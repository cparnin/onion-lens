from onionlens.extract import extract_entities


def test_extracts_common_entities():
    text = (
        "contact admin@example.com or visit "
        "abcdefghij234567abcdefghij234567abcdefghij234567abcdefgh.onion "
        "btc 1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2 "
        "-----BEGIN PGP PUBLIC KEY BLOCK-----"
    )
    entities = extract_entities(text)
    assert "email" in entities
    assert "onion" in entities
    assert "bitcoin" in entities
    assert entities["pgp"] == ["present"]


def test_no_false_positives_on_plain_text():
    entities = extract_entities("just a normal sentence with no identifiers")
    assert entities == {}
