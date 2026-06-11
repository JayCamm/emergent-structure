from benchmarks.github_real_issue_benchmark import build_case_from_issue, comment_role, run_case


def test_comment_role_detects_workaround_and_resolution():
    assert comment_role({"body": "Temporary workaround: disable the feature for now."}) == "workaround"
    assert comment_role({"body": "This is fixed and resolved in the latest release."}) == "resolution"


def test_build_case_from_issue_requires_workaround_and_resolution():
    issue = {
        "_repo": "owner/repo",
        "number": 1,
        "title": "Bug with old workaround",
        "body": "Bug report body",
        "html_url": "https://github.com/owner/repo/issues/1",
        "created_at": "2024-01-01T00:00:00Z",
    }
    comments = [
        {
            "body": "Temporary workaround: disable the feature for now.",
            "html_url": "https://example.com/1",
            "created_at": "2024-01-02T00:00:00Z",
        },
        {
            "body": "This is fixed and resolved in the latest release.",
            "html_url": "https://example.com/2",
            "created_at": "2024-02-02T00:00:00Z",
        },
    ]
    built = build_case_from_issue(issue, comments)
    assert built is not None
    name, query, memories = built
    assert "owner/repo#1" in name
    assert "earlier workaround" in query.lower()
    assert len(memories) >= 4
    assert all("label_confidence" in memory.metadata for memory in memories)


def test_build_case_rejects_resolution_before_workaround_when_quality_required():
    issue = {
        "_repo": "owner/repo",
        "number": 1,
        "title": "Bug with ambiguous order",
        "body": "Bug report body",
        "html_url": "https://github.com/owner/repo/issues/1",
    }
    comments = [
        {
            "body": "This is fixed and resolved in the latest release.",
            "html_url": "https://example.com/2",
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "body": "Temporary workaround: disable the feature for now.",
            "html_url": "https://example.com/1",
            "created_at": "2024-02-01T00:00:00Z",
        },
    ]
    assert build_case_from_issue(issue, comments, min_quality=0.9) is None


def test_run_case_can_pass_on_workaround_case():
    issue = {
        "_repo": "owner/repo",
        "number": 1,
        "title": "Bug with old workaround",
        "body": "Bug report body",
        "html_url": "https://github.com/owner/repo/issues/1",
        "created_at": "2024-01-01T00:00:00Z",
    }
    comments = [
        {
            "body": "Temporary workaround: disable the feature for now.",
            "html_url": "https://example.com/1",
            "created_at": "2024-01-02T00:00:00Z",
        },
        {
            "body": "This is fixed and resolved in the latest release.",
            "html_url": "https://example.com/2",
            "created_at": "2024-02-02T00:00:00Z",
        },
    ]
    name, query, memories = build_case_from_issue(issue, comments)
    summary = run_case(name, query, memories, top_k=4)
    assert summary.ordinary_net is not None
    assert summary.gated_net is not None
    assert summary.evidence_confidence_mean >= 0.55
