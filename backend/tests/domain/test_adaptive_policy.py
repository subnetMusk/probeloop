from probeloop.interview.domain.adaptive_policy import topic_windows
from probeloop.interview.domain.model import Topic, TopicCoverage


def test_windows_weight_priority_and_keep_time_spent_on_previous_topics() -> None:
    topics = (
        Topic("t1", "Evidence", rubric_kind="technical", priority=3),
        Topic("t2", "Reasoning", rubric_kind="technical"),
        Topic("t3", "Closing", rubric_kind="logistics"),
    )
    windows = topic_windows(topics, {}, {"t1": 100}, 200)
    assert [w.budget_s for w in windows[:2]] == [150, 50]
    assert windows[0].available
    exhausted = topic_windows(topics, {}, {"t1": 151}, 200)
    assert not exhausted[0].available
    assert not windows[-1].available
    covered = topic_windows(topics, {"t1": TopicCoverage.COVERED}, {}, 200)
    assert not covered[0].available
    assert covered[1].budget_s == 200


def test_ordinary_minimum_never_overrides_global_closing() -> None:
    topic = Topic("t1", "Reasoning", rubric_kind="technical")
    assert topic_windows((topic,), {}, {}, 1000)[0].budget_s == 240
    window = topic_windows((topic,), {}, {}, 0)[0]
    assert window.budget_s == 45
    assert not window.available
