# Candidate Preliminary Screening Tool

Decision-support web app (Python + Streamlit) that screens fictional applicants
against fixed eligibility rules. It only *suggests* a label; **no recruitment
decision is automated**. All data stays on the local machine.

## Files
| File | Purpose |
|---|---|
| `app.py` | Streamlit interface: upload, dashboard, filter, download |
| `screening_engine.py` | All rules and CSV handling (no UI code) |
| `test_screening.py` | 22 unit tests (standard library `unittest`) |
| `requirements.txt` | Dependencies |
| `HLL_Screening_Results.csv` | Exported results for the 200 supplied candidates |

## Run locally
```bash
python -m venv venv
venv\Scripts\activate          # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py           # opens http://localhost:8501
```
Then upload `HLL_AI_Screening_200_Candidates.csv` in the browser.

Run the tests: `python -m unittest -v`

## Rules applied
| Criterion | Requirement |
|---|---|
| Qualification | BE/B.Tech in Computer Science, IT or Software Engineering |
| Experience | At least 3 years |
| Mandatory skills | Python **and** SQL |
| Desirable (informational only) | AI, ML, NLP, GenAI, cloud, APIs, BI tools |

**Precedence:** definite failure -> *Not Qualified*; else anything missing /
unclear / needing verification -> *Manual Review*; else -> *Qualified*.

## Judgement calls (documented, not hidden)
* `Python`, `Python 3` and `Structured Query Language` are accepted as equivalents.
* `Py` and SQL dialects/products (`SQL Server`, `MySQL`, `PostgreSQL`...) are **not**
  auto-accepted -> *Manual Review* (equivalence must be verified by a person).
  If clear `SQL` is also listed, it counts as met.
* `Power BI`, `NoSQL`, and other skills are never treated as substitutes.
* Blank / malformed experience, blank skills, or an unrecognised qualification
  -> *Manual Review*. Nothing is guessed.
* `B.Sc`, `BCA`, `MCA`, `MBA` and BE/B.Tech in other branches are a definite
  failure. Postgraduate degrees (M.Tech/ME/MS) -> *Manual Review* (a BE may sit underneath).
* Decimal experience such as `3.5` is accepted; `2.9` fails.

## Results on the supplied file
200 candidates = 30 Qualified + 116 Not Qualified + 54 Manual Review.

## Demonstration candidates
| Case | Candidate |
|---|---|
| Qualified | C001 |
| Insufficient experience | C002 |
| Missing Python or SQL | C003 (no Python), C007 (no Python) |
| Ambiguous / incomplete | C021 (`Py`), C030 (blank experience) |
# Candidate-Screening
