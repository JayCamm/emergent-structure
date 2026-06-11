from benchmarks.external_benchmark_suite import all_cases, summarize_case


def test_external_benchmark_suite_has_expected_tracks():
    tracks = {case.track for case in all_cases()}
    assert "clean_control" in tracks
    assert "temporal_evidence" in tracks
    assert "revision_contradiction" in tracks
    assert "software_history" in tracks


def test_external_benchmark_suite_produces_summaries():
    summaries = [summarize_case(case) for case in all_cases()]
    assert len(summaries) == 4
    assert all(summary.ordinary_net is not None for summary in summaries)
    assert all(summary.gated_net is not None for summary in summaries)
