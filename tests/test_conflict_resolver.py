from agent.sync.conflict_resolver import ConflictResolver


def test_three_way_merge_combines_non_overlapping_edits() -> None:
    resolver = ConflictResolver()

    result = resolver.merge(
        "alpha\nbeta\ngamma\n",
        {
            "google": "ALPHA\nbeta\ngamma\n",
            "microsoft": "alpha\nbeta\nGAMMA\n",
        },
    )

    assert result.conflicted is False
    assert result.markdown == "ALPHA\nbeta\nGAMMA\n"


def test_three_way_merge_marks_overlapping_edits_without_choosing_a_winner() -> None:
    resolver = ConflictResolver()

    result = resolver.merge(
        "title\nshared paragraph\n",
        {
            "google": "title\nGoogle wording\n",
            "microsoft": "title\nMicrosoft wording\n",
        },
    )

    assert result.conflicted is True
    assert "<<<<<<< GOOGLE" in result.markdown
    assert "Google wording" in result.markdown
    assert "Microsoft wording" in result.markdown
    assert result.conflict_sources == ("google", "microsoft")


def test_identical_concurrent_edits_are_not_conflicts() -> None:
    result = ConflictResolver().merge(
        "old\n",
        {"google": "new\n", "microsoft": "new\n"},
    )

    assert result.conflicted is False
    assert result.markdown == "new\n"
