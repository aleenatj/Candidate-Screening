"""
screening_engine.py
-------------------
Rule engine for the HLL Lifecare preliminary candidate screening tool.

This module contains ALL the business logic and has no UI code, so it can be
tested on its own and explained line by line in an interview.

Decision support only: the output is a *suggested* label with a reason.
A human recruiter makes every final decision.

Classification precedence (from the brief):
    1. Any mandatory requirement DEFINITIVELY unmet  -> "Not Qualified"
    2. Else, any requirement missing / unclear / needing verification
                                                     -> "Manual Review"
    3. Else (all mandatory requirements clearly met) -> "Qualified"
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import IO, Union

import pandas as pd

# --------------------------------------------------------------------------
# 1. Constants
# --------------------------------------------------------------------------
QUALIFIED = "Qualified"
NOT_QUALIFIED = "Not Qualified"
MANUAL_REVIEW = "Manual Review"
STATUS_LABELS = [QUALIFIED, NOT_QUALIFIED, MANUAL_REVIEW]

# Outcome of checking ONE criterion (qualification / experience / a skill)
MET = "met"          # clearly satisfied
UNMET = "unmet"      # definitively failed
UNCLEAR = "unclear"  # missing, malformed or needs a human to verify

MIN_EXPERIENCE_YEARS = 3.0
MAX_PLAUSIBLE_EXPERIENCE = 50.0  # anything above is treated as a data error

# Columns the screening cannot run without.
REQUIRED_COLUMNS = [
    "Candidate_ID",
    "Candidate_Name",
    "Qualification",
    "Experience_Years",
    "Technical_Skills",
]
# Present in the supplied file, but not used by the rules.
OPTIONAL_COLUMNS = ["Current_Role", "Preferred_Location"]
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

# Text that really means "no value was given".
PLACEHOLDERS = {"", "nan", "none", "null", "n/a", "na", "-", "--", "unknown", "tbd"}


class ScreeningInputError(Exception):
    """Raised for unusable input; the message is safe to show to the user."""


@dataclass(frozen=True)
class CriterionResult:
    """Result of checking a single criterion."""

    outcome: str  # MET, UNMET or UNCLEAR
    detail: str   # human-readable, specific explanation


# --------------------------------------------------------------------------
# 2. Text helpers
# --------------------------------------------------------------------------
def clean_text(value) -> str:
    """Return a trimmed, single-spaced string; placeholders become ''."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return "" if text.lower() in PLACEHOLDERS else text


# --------------------------------------------------------------------------
# 3. Qualification rule: BE/B.Tech in Computer Science, IT or Software Eng.
# --------------------------------------------------------------------------
# Matched at the START of the text: degrees that are definitely not BE/B.Tech.
_NON_ENGINEERING_DEGREE = re.compile(
    r"^(mba|pgdm|mca|bca|bsc|b sc|msc|m sc|bba|ba|bcom|b com|mcom|diploma)\b"
)
# Postgraduate degrees: the person may hold a BE/B.Tech underneath -> verify.
_POSTGRAD_DEGREE = re.compile(
    r"^(mtech|m tech|me|ms|master of (engineering|technology)|phd|doctorate)\b"
)
_BE_BTECH = re.compile(
    r"\b(be|b e|btech|b tech|bachelor of engineering|bachelor of technology)\b"
)
_ALLOWED_BRANCH = re.compile(
    r"computer science|information technology|software engineering|\b(cse|cs|it)\b"
)
_OTHER_BRANCH = re.compile(
    r"electronics|electrical|mechanical|civil|chemical|instrumentation|"
    r"aeronautical|aerospace|biomedical|biotechnology|mining|production|"
    r"automobile|metallurgy|\b(ece|eee|ee)\b"
)


def _normalise_degree(text: str) -> str:
    t = text.lower().replace("&", " and ")
    t = t.replace(".", "")                 # "B.Tech" -> "btech", "B.E." -> "be"
    t = re.sub(r"[-_,()/]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def evaluate_qualification(raw) -> CriterionResult:
    text = clean_text(raw)
    if not text:
        return CriterionResult(UNCLEAR, "Qualification is blank, so the degree cannot be verified")

    norm = _normalise_degree(text)

    if _POSTGRAD_DEGREE.match(norm):
        return CriterionResult(
            UNCLEAR,
            f"Qualification '{text}' is a postgraduate degree; BE/B.Tech in CS/IT/SE not stated - verify",
        )
    if _NON_ENGINEERING_DEGREE.match(norm):
        return CriterionResult(
            UNMET, f"Qualification '{text}' is not a BE/B.Tech degree"
        )
    if _BE_BTECH.search(norm):
        if _ALLOWED_BRANCH.search(norm):
            return CriterionResult(MET, f"'{text}' meets the BE/B.Tech CS/IT/SE requirement")
        if _OTHER_BRANCH.search(norm):
            return CriterionResult(
                UNMET, f"Qualification '{text}' is not in Computer Science, IT or Software Engineering"
            )
        return CriterionResult(
            UNCLEAR, f"Qualification '{text}' has an unrecognised or missing branch - verify"
        )
    return CriterionResult(UNCLEAR, f"Qualification '{text}' is not recognised - verify manually")


# --------------------------------------------------------------------------
# 4. Experience rule: at least 3 years
# --------------------------------------------------------------------------
_EXPERIENCE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\+|years?|yrs?)?")


def evaluate_experience(raw) -> CriterionResult:
    text = clean_text(raw)
    if not text:
        return CriterionResult(UNCLEAR, "Experience_Years is blank, so experience cannot be verified")

    match = _EXPERIENCE_PATTERN.fullmatch(text.lower())
    if not match:
        return CriterionResult(UNCLEAR, f"Experience_Years '{text}' is not a valid number - verify")

    years = float(match.group(1))
    if years > MAX_PLAUSIBLE_EXPERIENCE:
        return CriterionResult(UNCLEAR, f"Experience_Years '{text}' is implausible - verify")
    unit = "year" if years == 1 else "years"
    if years < MIN_EXPERIENCE_YEARS:
        return CriterionResult(
            UNMET, f"Only {years:g} {unit} of experience (minimum {MIN_EXPERIENCE_YEARS:g})"
        )
    return CriterionResult(MET, f"{years:g} {unit} of experience (minimum {MIN_EXPERIENCE_YEARS:g})")


# --------------------------------------------------------------------------
# 5. Skills: normalise, then check Python AND SQL
# --------------------------------------------------------------------------
# Skill names are compared after lower-casing and replacing "-" / "_" by space.
_PYTHON_CLEAR = re.compile(r"python(?:\s*\d+(?:\.(?:\d+|x))*)?(?:\s+programming)?")
_SQL_CLEAR = {"sql", "structured query language"}

# Ambiguous: could be the mandatory skill, but a human must confirm.
_PYTHON_AMBIGUOUS = {"py", "py3", "py 3"}
_SQL_AMBIGUOUS = {
    "sql server", "ms sql server", "microsoft sql server", "mssql",
    "mysql", "postgresql", "postgres", "oracle", "oracle sql",
    "plsql", "pl sql", "t sql", "tsql", "sqlite",
}

# Desirable (NOT mandatory) skills - informational only.
DESIRABLE_SKILLS = {
    "AI": {"ai", "artificial intelligence", "computer vision"},
    "ML": {"ml", "machine learning", "deep learning", "mlops", "scikit learn", "pytorch", "tensorflow"},
    "NLP": {"nlp", "natural language processing"},
    "GenAI": {"genai", "gen ai", "generative ai", "llm", "rag", "langchain"},
    "Cloud": {"cloud", "aws", "azure", "gcp", "google cloud"},
    "APIs": {"api", "api development", "rest api", "restful api", "fastapi", "flask"},
    "BI tools": {"power bi", "tableau", "data visualization", "looker", "qlik"},
}


def split_skills(raw) -> list[str]:
    """Turn 'Python, SQL / Power BI' into ['python', 'sql', 'power bi']."""
    text = clean_text(raw).lower()
    if not text:
        return []
    # Protect slash-containing names before we split on "/".
    text = text.replace("pl/sql", "plsql").replace("ci/cd", "cicd")
    parts = re.split(r"[,;|\n]+|\s+and\s+|\s*&\s*|/", text)
    tokens = []
    for part in parts:
        token = re.sub(r"[-_]", " ", part)
        token = re.sub(r"\s+", " ", token).strip(" .")
        if token and token not in PLACEHOLDERS:
            tokens.append(token)
    return tokens


def _check_skill(name: str, tokens: list[str], is_clear, ambiguous: set[str]) -> CriterionResult:
    if any(is_clear(t) for t in tokens):
        return CriterionResult(MET, f"{name} listed")
    unclear_hits = [t for t in tokens if t in ambiguous]
    if unclear_hits:
        shown = ", ".join(f"'{t}'" for t in dict.fromkeys(unclear_hits))
        return CriterionResult(
            UNCLEAR, f"{name} not stated explicitly; found {shown} - equivalence needs verification"
        )
    listed = ", ".join(tokens[:6]) + ("..." if len(tokens) > 6 else "")
    return CriterionResult(UNMET, f"{name} is missing from Technical_Skills (listed: {listed})")


def evaluate_skills(raw) -> list[CriterionResult]:
    tokens = split_skills(raw)
    if not tokens:
        return [CriterionResult(
            UNCLEAR, "Technical_Skills is blank, so Python and SQL cannot be verified"
        )]
    return [
        _check_skill("Python", tokens, lambda t: bool(_PYTHON_CLEAR.fullmatch(t)), _PYTHON_AMBIGUOUS),
        _check_skill("SQL", tokens, lambda t: t in _SQL_CLEAR, _SQL_AMBIGUOUS),
    ]


def desirable_skills_found(raw) -> list[str]:
    tokens = set(split_skills(raw))
    return [label for label, names in DESIRABLE_SKILLS.items() if tokens & names]


# --------------------------------------------------------------------------
# 6. Combine the criteria into one label + reason
# --------------------------------------------------------------------------
def evaluate_candidate(row: dict) -> tuple[str, str]:
    """Return (status, reason) for one candidate record."""
    results = [
        evaluate_qualification(row.get("Qualification")),
        evaluate_experience(row.get("Experience_Years")),
        *evaluate_skills(row.get("Technical_Skills")),
    ]
    unmet = [r.detail for r in results if r.outcome == UNMET]
    unclear = [r.detail for r in results if r.outcome == UNCLEAR]

    if unmet:  # definite failure beats ambiguity
        reason = "Mandatory requirement not met: " + "; ".join(unmet) + "."
        if unclear:
            reason += " Also unverified: " + "; ".join(unclear) + "."
        return NOT_QUALIFIED, reason

    if unclear:
        return MANUAL_REVIEW, (
            "Needs human verification: " + "; ".join(unclear)
            + ". No mandatory requirement is definitively failed."
        )

    reason = "All mandatory requirements met: " + "; ".join(r.detail for r in results) + "."
    extras = desirable_skills_found(row.get("Technical_Skills"))
    reason += f" Desirable skills: {', '.join(extras)}." if extras else " No desirable skills listed."
    return QUALIFIED, reason


# --------------------------------------------------------------------------
# 7. DataFrame-level helpers: loading, validating, evaluating, summarising
# --------------------------------------------------------------------------
def load_candidates(source: Union[str, IO, bytes]) -> tuple[pd.DataFrame, list[str]]:
    """
    Read a CSV into a DataFrame of strings (nothing is converted or guessed).
    Returns (dataframe, warnings). Raises ScreeningInputError for unusable files.
    """
    def _read(encoding: str) -> pd.DataFrame:
        if isinstance(source, bytes):
            handle = io.BytesIO(source)
        else:
            handle = source
            if hasattr(handle, "seek"):
                handle.seek(0)
        return pd.read_csv(handle, dtype=str, keep_default_na=False, encoding=encoding)

    try:
        try:
            df = _read("utf-8-sig")
        except UnicodeDecodeError:
            df = _read("latin-1")
    except pd.errors.EmptyDataError:
        raise ScreeningInputError("The file is empty. Please upload a CSV that has a header row and data.")
    except pd.errors.ParserError as exc:
        raise ScreeningInputError(f"The file could not be parsed as a CSV ({exc}).")
    except Exception as exc:  # unreadable / not a CSV at all
        raise ScreeningInputError(f"The file could not be read as a CSV ({exc}).")

    warnings: list[str] = []

    # Match column names ignoring case and surrounding spaces.
    wanted = {c.lower(): c for c in ALL_COLUMNS}
    df.columns = [wanted.get(str(c).strip().lower(), str(c).strip()) for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ScreeningInputError(
            "Missing mandatory column(s): " + ", ".join(missing)
            + ". Columns found: " + ", ".join(df.columns) + "."
        )
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            warnings.append(f"Optional column '{col}' not found; it is not used in screening.")

    blank_rows = df.apply(lambda col: col.astype(str).str.strip() == "").all(axis=1)
    if blank_rows.any():
        warnings.append(f"{int(blank_rows.sum())} completely blank row(s) were ignored.")
        df = df[~blank_rows].reset_index(drop=True)

    if df.empty:
        raise ScreeningInputError("The file has a header but no candidate rows.")

    ids = df["Candidate_ID"].astype(str).str.strip()
    dup = ids[(ids != "") & ids.duplicated(keep=False)]
    if not dup.empty:
        warnings.append(
            f"Duplicate Candidate_ID values found: {', '.join(sorted(dup.unique()))}. "
            "Every row is still evaluated separately."
        )
    return df, warnings


def evaluate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add Expected_Status and Reason to every row (exactly one label each)."""
    statuses, reasons = [], []
    for record in df.to_dict(orient="records"):
        try:
            status, reason = evaluate_candidate(record)
        except Exception as exc:  # never let one bad row crash the whole run
            status = MANUAL_REVIEW
            reason = f"Record could not be evaluated automatically ({type(exc).__name__}); review manually."
        statuses.append(status)
        reasons.append(reason)
    out = df.copy()
    out["Expected_Status"] = statuses
    out["Reason"] = reasons
    return out


def summarise(results: pd.DataFrame) -> dict:
    """Counts for the dashboard, plus a check that the totals reconcile."""
    total = len(results)
    counts = {label: int((results["Expected_Status"] == label).sum()) for label in STATUS_LABELS}
    return {"total": total, **counts, "reconciles": sum(counts.values()) == total}
