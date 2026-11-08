from api.graph.citations import check_citations


def test_valid_citations_are_kept_and_grounded():
    check = check_citations("Keep it cold [1]. Log it hourly [2].", [1, 2, 3])
    assert check.text == "Keep it cold [1]. Log it hourly [2]."
    assert check.cited == {1, 2}
    assert check.grounded


def test_invented_citation_is_removed_and_not_grounded():
    check = check_citations("Keep it cold [1]. Made up fact [7].", [1, 2])
    assert check.text == "Keep it cold [1]. Made up fact."
    assert check.invalid == {7}
    assert not check.grounded


def test_grouped_citations_are_split_for_the_frontend():
    check = check_citations("Both say so [1, 2].", [1, 2])
    assert check.text == "Both say so [1][2]."


def test_answer_without_citations_is_not_grounded():
    check = check_citations("I couldn't find this in the files you selected.", [1])
    assert not check.cited
    assert not check.grounded


def test_markdown_links_are_untouched():
    check = check_citations("See [the guide](https://example.com) [1].", [1])
    assert check.text == "See [the guide](https://example.com) [1]."
