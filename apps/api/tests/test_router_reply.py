from api.graph.prompts import parse_router_reply


def test_two_line_reply():
    assert parse_router_reply("route: database\nquestion: Sales in Q3?", "And Q3?") == (True, "Sales in Q3?")


def test_markdown_and_capitals_are_tolerated():
    reply = "**Route:** Documents\n**Question:** What does the SOP say about loggers?"
    assert parse_router_reply(reply, "loggers?") == (False, "What does the SOP say about loggers?")


def test_one_word_reply_still_routes():
    assert parse_router_reply("database", "How many orders?") == (True, "How many orders?")


def test_missing_or_rambling_question_falls_back_to_the_original():
    assert parse_router_reply("route: documents", "loggers?") == (False, "loggers?")
    assert parse_router_reply(f"route: documents\nquestion: {'x' * 600}", "loggers?") == (False, "loggers?")


def test_unreadable_reply_means_documents():
    assert parse_router_reply("I'm not sure.", "What is this?") == (False, "What is this?")
