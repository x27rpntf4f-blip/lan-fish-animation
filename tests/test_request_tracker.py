from fishmesh.request_tracker import RequestTracker


def test_request_is_retried_after_deadline() -> None:
    now = [100.0]
    tracker = RequestTracker(retry_after=3.0, clock=lambda: now[0])

    assert tracker.should_request("Purple")
    tracker.mark_requested("Purple")
    assert not tracker.should_request("Purple")

    now[0] = 103.0

    assert tracker.should_request("Purple")


def test_completion_removes_pending_request() -> None:
    tracker = RequestTracker(retry_after=3.0)

    tracker.mark_requested("Purple")
    tracker.mark_complete("Purple")

    assert tracker.should_request("Purple")


def test_clear_allows_all_pending_requests_immediately() -> None:
    now = [100.0]
    tracker = RequestTracker(retry_after=3.0, clock=lambda: now[0])
    tracker.mark_requested("Purple")
    tracker.mark_requested("Blue")

    tracker.clear()

    assert tracker.should_request("Purple")
    assert tracker.should_request("Blue")
