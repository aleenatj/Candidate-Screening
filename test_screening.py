"""
Unit tests for the screening rules. Run with:  python -m unittest -v
Uses only the standard library (no pytest needed).
"""

import io
import unittest

import pandas as pd

from screening_engine import (
    MANUAL_REVIEW, NOT_QUALIFIED, QUALIFIED,
    ScreeningInputError, evaluate_candidate, evaluate_dataframe,
    load_candidates, split_skills, summarise,
)


def status(qualification="B.Tech Computer Science", years="5", skills="Python, SQL"):
    return evaluate_candidate(
        {"Qualification": qualification, "Experience_Years": years, "Technical_Skills": skills}
    )[0]


class DemoCases(unittest.TestCase):
    """The four minimum demonstration cases from the brief."""

    def test_qualified(self):
        self.assertEqual(status(), QUALIFIED)

    def test_insufficient_experience(self):
        self.assertEqual(status(years="2"), NOT_QUALIFIED)

    def test_missing_python_or_sql(self):
        self.assertEqual(status(skills="SQL, Power BI"), NOT_QUALIFIED)
        self.assertEqual(status(skills="Python, Power BI"), NOT_QUALIFIED)

    def test_incomplete_record(self):
        self.assertEqual(status(years=""), MANUAL_REVIEW)


class SkillNormalisation(unittest.TestCase):
    def test_equivalent_expressions_are_qualified(self):
        self.assertEqual(status(skills="  python 3 ,  STRUCTURED QUERY LANGUAGE "), QUALIFIED)
        self.assertEqual(status(skills="Python3; SQL"), QUALIFIED)
        self.assertEqual(status(skills="Python/SQL"), QUALIFIED)

    def test_power_bi_is_not_a_sql_substitute(self):
        self.assertEqual(status(skills="Python, Power BI"), NOT_QUALIFIED)

    def test_nosql_is_not_sql(self):
        self.assertEqual(status(skills="Python, NoSQL"), NOT_QUALIFIED)

    def test_ambiguous_skills_need_review(self):
        self.assertEqual(status(skills="Py, SQL"), MANUAL_REVIEW)
        self.assertEqual(status(skills="Python, SQL Server"), MANUAL_REVIEW)

    def test_clear_sql_wins_over_dialect(self):
        self.assertEqual(status(skills="Python, SQL, PostgreSQL"), QUALIFIED)

    def test_plsql_is_not_split_into_sql(self):
        self.assertEqual(split_skills("PL/SQL, Python"), ["plsql", "python"])

    def test_blank_skills_need_review(self):
        self.assertEqual(status(skills=""), MANUAL_REVIEW)


class QualificationAndExperience(unittest.TestCase):
    def test_accepted_degrees(self):
        for q in ["BE Computer Science", "B.E. Information Technology", "b.tech software engineering"]:
            self.assertEqual(status(qualification=q), QUALIFIED, q)

    def test_wrong_branch_or_degree(self):
        for q in ["B.Tech Mechanical Engineering", "B.Sc Computer Science", "MCA", "MBA", "BCA"]:
            self.assertEqual(status(qualification=q), NOT_QUALIFIED, q)

    def test_unclear_degree(self):
        for q in ["", "M.Tech Computer Science", "B.Tech", "Certificate in AI"]:
            self.assertEqual(status(qualification=q), MANUAL_REVIEW, q)

    def test_experience_boundaries(self):
        self.assertEqual(status(years="3"), QUALIFIED)
        self.assertEqual(status(years="2.9"), NOT_QUALIFIED)
        self.assertEqual(status(years="3.5"), QUALIFIED)

    def test_malformed_experience(self):
        for y in ["abc", "-2", "999"]:
            self.assertEqual(status(years=y), MANUAL_REVIEW, y)


class Precedence(unittest.TestCase):
    def test_definite_failure_beats_ambiguity(self):
        # blank experience (unclear) + MBA (definite fail) -> Not Qualified
        self.assertEqual(status(qualification="MBA", years=""), NOT_QUALIFIED)
        # Py (unclear) + 1 year (definite fail) -> Not Qualified
        self.assertEqual(status(years="1", skills="Py, SQL"), NOT_QUALIFIED)


class FileHandling(unittest.TestCase):
    HEADER = "Candidate_ID,Candidate_Name,Qualification,Experience_Years,Technical_Skills,Current_Role,Preferred_Location\n"

    def test_missing_column_is_reported(self):
        with self.assertRaises(ScreeningInputError) as ctx:
            load_candidates(b"Candidate_ID,Candidate_Name\nC1,A\n")
        self.assertIn("Qualification", str(ctx.exception))

    def test_empty_file(self):
        with self.assertRaises(ScreeningInputError):
            load_candidates(b"")

    def test_header_only(self):
        with self.assertRaises(ScreeningInputError):
            load_candidates(self.HEADER.encode())

    def test_totals_reconcile_and_one_label_each(self):
        csv = self.HEADER + "C1,A,BE Computer Science,5,\"Python, SQL\",x,y\nC2,B,MBA,6,Excel,x,y\nC3,C,BE Computer Science,,\"Python, SQL\",x,y\n"
        df, _ = load_candidates(csv.encode())
        out = evaluate_dataframe(df)
        s = summarise(out)
        self.assertEqual((s["total"], s[QUALIFIED], s[NOT_QUALIFIED], s[MANUAL_REVIEW]), (3, 1, 1, 1))
        self.assertTrue(s["reconciles"])
        self.assertTrue(out["Expected_Status"].isin([QUALIFIED, NOT_QUALIFIED, MANUAL_REVIEW]).all())

    def test_original_columns_preserved(self):
        csv = self.HEADER + "C1,A,BE Computer Science,5,\"Python, SQL\",Dev,Kochi\n"
        df, _ = load_candidates(csv.encode())
        out = evaluate_dataframe(df)
        self.assertEqual(list(out.columns), list(df.columns) + ["Expected_Status", "Reason"])


if __name__ == "__main__":
    unittest.main()
