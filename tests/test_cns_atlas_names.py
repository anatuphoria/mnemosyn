import pytest

from cns_atlas import Atlas
from cns_atlas.names import NameIndex, linked_html


@pytest.fixture
def index():
    phrases = {"thalamus": 1, "ventral lateral nucleus of the thalamus": 2, "pons": 3,
               "precentral gyrus": 10, "brain": 4}
    return NameIndex(phrases, {11: 10, 12: 10}, frozenset({"brain"}))


def targets(links):
    return [link.target for link in links]


def test_the_longest_phrase_wins(index):
    text = "Relays through the ventral lateral nucleus of the thalamus."
    assert targets(index.find(text)) == [2]


def test_only_the_first_mention_links(index):
    assert targets(index.find("The thalamus and the thalamus.")) == [1]


def test_a_phrase_inside_a_word_does_not_link(index):
    assert index.find("It responds slowly.") == []


def test_a_capitalised_mention_links_and_keeps_its_letters(index):
    text = "Thalamus relays."
    assert linked_html(text, index.find(text)) == "<a href='structure:1'>Thalamus</a> relays."


def test_the_shown_part_and_its_whole_stay_plain(index):
    assert index.find("The precentral gyrus.", shown=11) == []
    assert index.find("The precentral gyrus.", shown=10) == []


def test_stop_words_stay_plain(index):
    assert index.find("The brain.") == []


def test_text_is_escaped_inside_and_outside_links(index):
    text = "a < b & the pons > c"
    assert linked_html(text, index.find(text)) == (
        "a &lt; b &amp; the <a href='structure:3'>pons</a> &gt; c")


def test_citation_numbers_are_kept(index):
    text = "Into the pons [2]."
    assert linked_html(text, index.find(text)).endswith("</a> [2].")


def test_the_atlas_index_maps_names_and_synonyms_to_the_whole_part(toy_atlas):
    atlas = Atlas.open(toy_atlas)
    links = atlas.names.find("Projects to the alpha gyrus and the first gyrus.")
    assert targets(links) == [100]
    assert atlas.names.home_of(101) == 100
