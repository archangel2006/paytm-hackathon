from datetime import timedelta
import pytest
from server.adapters.clock import Clock
from server.scheduler.loop import Scheduler
from server.db.repo import PlatformRepo

def test_pl06_clock_advance_and_reset():
    clk = Clock()
    t0 = clk.now()

    clk.advance(hours=24)
    t1 = clk.now()
    diff = (t1 - t0).total_seconds()
    assert abs(diff - 86400) < 5

    clk.reset()
    t2 = clk.now()
    diff_reset = abs((t2 - t0).total_seconds())
    assert diff_reset < 5

def test_pl07_scheduler_due_job_execution(test_repo):
    from server.adapters.clock import clock
    clock.reset()

    # Schedule a job for +2 hours
    merchant = test_repo.create_lead("+919999900004")
    run_time = clock.now() + timedelta(hours=2)
    job = test_repo.schedule_job(merchant.id, "activation_check", run_time)
    assert job.status == "pending"

    calls = []
    def dummy_timer_handler(m_id, reason):
        calls.append((m_id, reason))

    sched = Scheduler(timer_handler=dummy_timer_handler)

    # 1. Before advance: job is not due
    due_before = sched.run_due_jobs_once(db=test_repo.db)
    assert len(due_before) == 0
    assert len(calls) == 0

    # 2. Advance clock by 3 hours
    clock.advance(hours=3)
    due_after = sched.run_due_jobs_once(db=test_repo.db)
    assert len(due_after) == 1
    assert due_after[0]["status"] == "done"
    assert len(calls) == 1
    assert calls[0] == (merchant.id, "activation_check")

    # 3. Clean up clock
    clock.reset()

