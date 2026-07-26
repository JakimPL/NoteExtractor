from note_extractor.timeline.piecewise import PiecewiseTimeline, Segment


def test_default_holds_ahead_of_the_first_change() -> None:
    timeline = PiecewiseTimeline([(100, "second")], "first")

    assert timeline.value_at(0) == "first"
    assert timeline.value_at(99) == "first"
    assert timeline.value_at(100) == "second"


def test_changes_are_ordered_by_tick() -> None:
    timeline = PiecewiseTimeline([(200, "third"), (100, "second")], "first")

    assert timeline.segments == (
        Segment(start_tick=0, value="first"),
        Segment(start_tick=100, value="second"),
        Segment(start_tick=200, value="third"),
    )


def test_the_last_change_on_a_tick_holds() -> None:
    timeline = PiecewiseTimeline([(100, "earlier"), (100, "later")], "first")

    assert timeline.value_at(100) == "later"
    assert len(timeline.segments) == 2


def test_a_change_on_tick_zero_replaces_the_default() -> None:
    timeline = PiecewiseTimeline([(0, "stated")], "first")

    assert timeline.segments == (Segment(start_tick=0, value="stated"),)


def test_segment_at_reports_the_stretch_holding_on_a_tick() -> None:
    timeline = PiecewiseTimeline([(100, "second")], "first")

    assert timeline.index_at(150) == 1
    assert timeline.segment_at(150) == Segment(start_tick=100, value="second")


def test_lookups_below_tick_zero_read_the_first_segment() -> None:
    timeline = PiecewiseTimeline([(100, "second")], "first")

    assert timeline.index_at(-1) == 0
    assert timeline.value_at(-1) == "first"


def test_a_timeline_without_changes_holds_the_default() -> None:
    timeline: PiecewiseTimeline[str] = PiecewiseTimeline([], "only")

    assert timeline.segments == (Segment(start_tick=0, value="only"),)
    assert timeline.value_at(10_000) == "only"
