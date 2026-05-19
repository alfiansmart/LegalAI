from backend.agents import slash


def test_is_slash():
    assert slash.is_slash("/find perjanjian")
    assert slash.is_slash("   /draft nda")
    assert not slash.is_slash("hello")


def test_parse_find_routes_to_asisten():
    intent = slash.parse("/find syarat sah perjanjian")
    assert intent is not None
    assert intent.command == "find"
    assert intent.agent == "asisten_hukum"
    msg = slash.to_user_message(intent)
    assert "peraturan_search" in msg
    assert "syarat sah perjanjian" in msg


def test_parse_draft_uses_drafter_persona():
    intent = slash.parse("/draft nda parties=PT Alpha;PT Beta")
    assert intent.command == "draft"
    assert intent.agent == "drafter"


def test_parse_review_with_multiline_body():
    intent = slash.parse("/review\nPasal 1\nFulan setuju...")
    assert intent.command == "review"
    body = " ".join(intent.args)
    assert "Pasal 1" in body
    msg = slash.to_user_message(intent)
    assert "contract_review" in msg


def test_parse_plan_sets_plan_mode():
    intent = slash.parse("/plan tolong analisa PKWT ini")
    assert intent.plan_mode is True


def test_unknown_returns_help_text():
    intent = slash.parse("/notreal foo")
    assert intent.help_text is not None
    assert "tidak dikenal" in intent.help_text.lower()


def test_help_lists_commands():
    intent = slash.parse("/help")
    assert intent.help_text and "/find" in intent.help_text
    assert "/draft" in intent.help_text
