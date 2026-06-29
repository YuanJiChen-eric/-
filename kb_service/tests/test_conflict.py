"""导入矛盾知识处理 — 单元测试"""
import unittest
from datetime import datetime

from kb_conflict import (
    coexist_priority_boost,
    parse_date,
    parse_version,
    plan_import_action,
    resolve_conflict_action,
    sort_search_results,
)


class TestDateVersionParsing(unittest.TestCase):
    def test_parse_date_iso(self):
        self.assertEqual(
            parse_date({"date": "2026-06-01"}).strftime("%Y-%m-%d"),
            "2026-06-01",
        )

    def test_parse_version(self):
        self.assertEqual(parse_version({"version": 3}), 3)


class TestResolveConflict(unittest.TestCase):
    def test_same_priority_newer_date_supersedes(self):
        new = {"type": "ops_doc", "date": "2026-06-10"}
        old = {"type": "ops_doc", "date": "2026-01-01"}
        self.assertEqual(resolve_conflict_action(new, old), "supersede")

    def test_same_priority_older_date_rejected(self):
        new = {"type": "ops_doc", "date": "2025-01-01"}
        old = {"type": "ops_doc", "date": "2026-06-01"}
        self.assertEqual(resolve_conflict_action(new, old), "reject")

    def test_same_priority_higher_version_supersedes(self):
        new = {"type": "ops_doc", "version": 2}
        old = {"type": "ops_doc", "version": 1}
        self.assertEqual(resolve_conflict_action(new, old), "supersede")

    def test_same_priority_no_date_version_coexist(self):
        new = {"type": "ops_doc"}
        old = {"type": "ops_doc"}
        self.assertEqual(resolve_conflict_action(new, old), "coexist")

    def test_coexist_priority_boost(self):
        boosted = coexist_priority_boost({"type": "ops_doc"}, {"type": "ops_doc"})
        self.assertEqual(boosted, 101)


class TestPlanImportAction(unittest.TestCase):
    def test_coexist_action(self):
        plan = plan_import_action(
            new_answer="周五全量",
            new_metadata={"type": "ops_doc"},
            existing_id="kb_1",
            existing_answer="周一全量",
            existing_metadata={"type": "ops_doc"},
            similarity_score=0.88,
            handle_conflicts=True,
        )
        self.assertEqual(plan["action"], "coexist")
        self.assertEqual(plan["boosted_priority"], 101)

    def test_date_supersede_plan(self):
        plan = plan_import_action(
            new_answer="新答案",
            new_metadata={"type": "ops_doc", "date": "2026-06-10"},
            existing_id="kb_1",
            existing_answer="旧答案",
            existing_metadata={"type": "ops_doc", "date": "2026-01-01"},
            similarity_score=0.9,
            handle_conflicts=True,
        )
        self.assertEqual(plan["action"], "supersede")


class TestSearchSort(unittest.TestCase):
    def test_sort_by_priority(self):
        rows = [
            {"score": 0.9, "metadata": {"source": "ticket", "priority": 60}},
            {"score": 0.7, "metadata": {"type": "ops_doc", "priority": 100}},
            {"score": 0.95, "metadata": {"priority": 101}},
        ]
        sorted_rows = sort_search_results(rows)
        self.assertEqual(get_priority_from_row(sorted_rows[0]), 101)
        self.assertEqual(get_priority_from_row(sorted_rows[1]), 100)


def get_priority_from_row(row):
    from kb_conflict import get_priority

    return get_priority(row.get("metadata"))


if __name__ == "__main__":
    unittest.main()
