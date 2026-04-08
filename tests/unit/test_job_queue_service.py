"""Unit tests for api/services/job_queue_service.py — JobQueueService.

Pure static tests — DB and handler functions are mocked.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


from api.services.job_queue_service import (
    JobQueueService,
    _execute_job,
    _fail_job,
    register_handler,
    _HANDLERS,
)


def _mock_db():
    return MagicMock()


def _mock_job(**kwargs):
    job = MagicMock()
    job.id = kwargs.get("id", 1)
    job.job_type = kwargs.get("job_type", "test_job")
    job.payload = kwargs.get("payload", {"orgnr": "123456789"})
    job.status = kwargs.get("status", "running")
    job.attempts = kwargs.get("attempts", 1)
    job.max_attempts = kwargs.get("max_attempts", 3)
    job.error = kwargs.get("error", None)
    job.finished_at = kwargs.get("finished_at", None)
    return job


# ── register_handler ──────────────────────────────────────────────────────────

def test_register_handler_stores_function():
    def fn(db, payload):
        return None
    register_handler("test_register_unique", fn)
    assert _HANDLERS["test_register_unique"] is fn
    del _HANDLERS["test_register_unique"]


def test_register_handler_overwrites_existing():
    def fn1(db, p):
        return None
    def fn2(db, p):
        return "v2"
    register_handler("overwrite_test", fn1)
    register_handler("overwrite_test", fn2)
    assert _HANDLERS["overwrite_test"] is fn2
    del _HANDLERS["overwrite_test"]


# ── JobQueueService.enqueue ───────────────────────────────────────────────────

def test_enqueue_adds_job_and_commits():
    db = _mock_db()
    JobQueueService(db).enqueue("pdf_extract", {"orgnr": "123"})
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()


def test_enqueue_sets_job_type_and_payload():
    db = _mock_db()
    JobQueueService(db).enqueue("send_email", {"to": "a@b.com"})
    added = db.add.call_args[0][0]
    assert added.job_type == "send_email"
    assert added.payload == {"to": "a@b.com"}


def test_enqueue_sets_status_pending_and_attempts_zero():
    db = _mock_db()
    JobQueueService(db).enqueue("any_job")
    added = db.add.call_args[0][0]
    assert added.status == "pending"
    assert added.attempts == 0


def test_enqueue_sets_created_at_and_scheduled_at():
    db = _mock_db()
    before = datetime.now(timezone.utc)
    JobQueueService(db).enqueue("test_job")
    added = db.add.call_args[0][0]
    assert added.created_at >= before
    assert added.scheduled_at >= before


def test_enqueue_accepts_none_payload():
    db = _mock_db()
    JobQueueService(db).enqueue("simple_job", None)
    added = db.add.call_args[0][0]
    assert added.payload is None


# ── _execute_job ──────────────────────────────────────────────────────────────

def test_execute_job_calls_handler_with_db_and_payload():
    handler = MagicMock()
    job = _mock_job(job_type="exec_test", payload={"key": "value"})
    db = _mock_db()

    _HANDLERS["exec_test"] = handler
    try:
        _execute_job(db, job)
    finally:
        del _HANDLERS["exec_test"]

    handler.assert_called_once_with(db, {"key": "value"})


def test_execute_job_sets_status_done_on_success():
    handler = MagicMock()
    job = _mock_job(job_type="done_test")
    db = _mock_db()

    _HANDLERS["done_test"] = handler
    try:
        _execute_job(db, job)
    finally:
        del _HANDLERS["done_test"]

    assert job.status == "done"
    assert job.finished_at is not None
    db.commit.assert_called_once()


def test_execute_job_calls_fail_job_when_no_handler():
    job = _mock_job(job_type="unregistered_xyz_type")
    db = _mock_db()

    with patch("api.services.job_queue_service._fail_job") as mock_fail:
        _execute_job(db, job)

    mock_fail.assert_called_once()
    error_msg = mock_fail.call_args[0][2]
    assert "unregistered_xyz_type" in error_msg


def test_execute_job_calls_fail_job_when_handler_raises():
    handler = MagicMock(side_effect=RuntimeError("handler crashed"))
    job = _mock_job(job_type="crash_test")
    db = _mock_db()

    _HANDLERS["crash_test"] = handler
    try:
        with patch("api.services.job_queue_service._fail_job") as mock_fail:
            _execute_job(db, job)
    finally:
        del _HANDLERS["crash_test"]

    mock_fail.assert_called_once()
    assert "handler crashed" in mock_fail.call_args[0][2]


# ── _fail_job ─────────────────────────────────────────────────────────────────

def test_fail_job_sets_failed_status_when_max_attempts_reached():
    job = _mock_job(attempts=3, max_attempts=3)
    db = _mock_db()
    _fail_job(db, job, "something went wrong")
    assert job.status == "failed"


def test_fail_job_sets_pending_status_when_attempts_below_max():
    job = _mock_job(attempts=1, max_attempts=3)
    db = _mock_db()
    _fail_job(db, job, "transient error")
    assert job.status == "pending"


def test_fail_job_sets_finished_at_only_when_failed():
    job = _mock_job(attempts=3, max_attempts=3)
    db = _mock_db()
    _fail_job(db, job, "final failure")
    assert job.finished_at is not None


def test_fail_job_clears_finished_at_when_pending():
    job = _mock_job(attempts=1, max_attempts=3)
    db = _mock_db()
    _fail_job(db, job, "will retry")
    assert job.finished_at is None


def test_fail_job_truncates_long_error_to_500_chars():
    job = _mock_job(attempts=3, max_attempts=3)
    db = _mock_db()
    long_error = "x" * 1000
    _fail_job(db, job, long_error)
    assert len(job.error) == 500


def test_fail_job_commits():
    job = _mock_job(attempts=1, max_attempts=3)
    db = _mock_db()
    _fail_job(db, job, "error")
    db.commit.assert_called_once()


# ── JobQueueService.process_pending ──────────────────────────────────────────

def test_process_pending_returns_zero_when_no_job():
    db_factory = MagicMock()
    db = _mock_db()
    db_factory.return_value = db

    with patch("api.services.job_queue_service._claim_next", return_value=None):
        result = JobQueueService.process_pending(db_factory=db_factory)

    assert result == 0
    db.close.assert_called_once()


def test_process_pending_returns_one_when_job_processed():
    db_factory = MagicMock()
    db = _mock_db()
    db_factory.return_value = db
    job = _mock_job()

    with patch("api.services.job_queue_service._claim_next", return_value=job):
        with patch("api.services.job_queue_service._execute_job") as mock_exec:
            result = JobQueueService.process_pending(db_factory=db_factory)

    assert result == 1
    mock_exec.assert_called_once_with(db, job)
    db.close.assert_called_once()


def test_process_pending_closes_db_on_exception():
    db_factory = MagicMock()
    db = _mock_db()
    db_factory.return_value = db

    with patch("api.services.job_queue_service._claim_next", side_effect=Exception("DB error")):
        result = JobQueueService.process_pending(db_factory=db_factory)

    assert result == 0
    db.close.assert_called_once()
