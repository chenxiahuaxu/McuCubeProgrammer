"""Logger 单例单元测试 — 线程安全性验证。"""

from __future__ import annotations

import threading

from src.utils.logger import Logger, LogEntry, add_log


class TestLogEntry:
    def test_log_entry_creation(self):
        entry = LogEntry("INFO", "hello")
        assert entry.level == "INFO"
        assert entry.message == "hello"
        assert ":" in entry.timestamp

    def test_log_entry_repr(self):
        entry = LogEntry("ERROR", "test error")
        r = repr(entry)
        assert "ERROR" in r
        assert "test error" in r


class TestLoggerSingleton:
    def test_same_instance(self):
        a = Logger()
        b = Logger()
        assert a is b

    def test_add_log_creates_entries(self):
        logger = Logger()
        logger.clear()
        logger.add("INFO", "test")
        entries = logger.get_all()
        assert len(entries) == 1
        assert entries[0].message == "test"

    def test_add_log_multiple_entries(self):
        logger = Logger()
        logger.clear()
        for i in range(5):
            logger.add("INFO", f"msg_{i}")
        assert len(logger.get_all()) == 5

    def test_get_all_returns_copy(self):
        logger = Logger()
        logger.clear()
        logger.add("INFO", "original")
        entries = logger.get_all()
        entries.clear()
        assert len(logger.get_all()) == 1

    def test_clear_empties_entries(self):
        logger = Logger()
        logger.clear()
        logger.add("INFO", "data")
        logger.clear()
        assert len(logger.get_all()) == 0

    def test_set_callback(self):
        logger = Logger()
        logger.clear()
        received = []

        def cb(entry):
            received.append(entry)

        logger.set_callback(cb)
        logger.add("WARN", "callback test")
        assert len(received) == 1
        assert received[0].message == "callback test"

    def test_buffer_trimming(self):
        """1200 次 add：第 1001 次触发 trim 到 500，后续 199 次追加，共 699 条。"""
        logger = Logger()
        logger.clear()
        for i in range(1200):
            logger.add("INFO", f"msg_{i}")
        entries = logger.get_all()
        # 首次超过 1000 时 trim 到 500，之后未再超过 1000，所以是 500 + (1200-1001) = 699
        assert len(entries) == 699

    def test_thread_safety_parallel_add(self):
        logger = Logger()
        logger.clear()
        errors = []

        def worker(thread_id):
            try:
                for i in range(200):
                    logger.add("INFO", f"t{thread_id}_m{i}")
            except Exception as e:  # pylint: disable=broad-exception-caught  # OK: test cleanup
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        entries = logger.get_all()
        assert len(entries) > 0
        assert len(entries) <= 1000


class TestAddLogFunction:  # pylint: disable=too-few-public-methods
    def test_add_log_uses_singleton(self):
        logger = Logger()
        logger.clear()
        add_log("DONE", "global func test")
        assert len(logger.get_all()) == 1
        assert logger.get_all()[0].level == "DONE"
