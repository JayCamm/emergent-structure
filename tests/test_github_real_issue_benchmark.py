from benchmarks.github_real_issue_benchmark import build_case_from_issue, run_case


def test_build_case_from_issue_requires_workaround_and_resolution():
    issue = {
        "_repo": "owner/repo",
        "number": 1,
        "title": "Bug with old workaround",
        "body": "Bug report body",
        "html_url": "https://github.com/owner/repo/issues/1",
    }
    comments = [
        {"body": "Temporary workaround: disable the feature for now.", "html_url": "https://example.com/1"},
        {"body": "This is fixed and resolved in the latest release.", "html_url": "https://example.com/2"},
    ]
    built = build_case_from_issue(issue, comments)
    assert built is not None
    name, query, memories = built
    assert "owner/repo#1" in name
    assert "old workaround" in query.lower()
    assert len(memories) >= 4


def test_run_case_can_pass_on_workaround_case():
    issue = {
        "_repo": "owner/repo",
        "number": 1,
        "title": "Bug with old workaround",
        "body": "Bug report body",
        "html_url": "https://github.com/owner/repo/issues/1",
    }
    comments = [
        {"body": "Temporary workaround: disable the feature for now.", "html_url": "https://example.com/1"},
        {"body": "This is fixed and resolved in the latest release.", "html_url": "https://example.com/2"},
    ]
    name, query, memories = build_case_from_issue(issue, comments)
    summary = run_case(name, query, memories, top_k=4)
    assert summary.ordinary_net is not None
    assert summary.gated_net is not None
