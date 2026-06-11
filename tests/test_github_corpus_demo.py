from examples.github_corpus_demo import age_risk, keyword_score


def test_keyword_score_detects_project_terms():
    score = keyword_score("persistence memory retrieval gate architecture", {"persistence", "memory", "retrieval", "gate"})
    assert score > 0.5


def test_age_risk_handles_missing_date():
    assert age_risk(None) > 0
