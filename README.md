# DPIA-Privacy-Impact-Assessment

[![GitHub](https://img.shields.io/badge/GitHub-GugaValenca-181717?style=flat&logo=github&logoColor=white)](https://github.com/GugaValenca)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-gugavalenca-0A66C2?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/gugavalenca/)

A guided Data Protection Impact Assessment (DPIA) tool: a 5-step wizard
walks through describing a proposed processing activity, judging its
necessity and proportionality, flagging applicable risk factors, and
documenting mitigations — ending in a calculated risk score, a
recommendation, and an exportable, audit-structured PDF report.

Where [Project 2 (Data-Mapping-ROPA)](https://github.com/GugaValenca/data-mapping-ropa)
records processing activities already running, this project assesses a
new one **before** it launches. Both use the same fictional NimbusCart
e-commerce company; this one's seeded scenario is NimbusCart proposing an
AI-powered product recommendation engine.

## The problem it solves

A real DPIA is a judgment call — necessity, proportionality, and risk
aren't things a spreadsheet computes for you — but the process around
that judgment call is still usually a Word document template passed
around by email: easy to fill in inconsistently, easy to skip a section
of, and hard to turn into a comparable risk score across different
proposals. This tool keeps the judgment calls (they're free-text fields,
on purpose) but structures everything around them: a fixed workflow that
can't be skipped ahead, a risk factor catalog with consistent severity
weights, and a scoring function that combines the two the same way every
time.

## What it does

- **5-step guided wizard** — processing description → necessity &
  proportionality → risk factor selection → mitigation measures → review
  & risk score. Each step is guarded server-side: reaching step 4 without
  having completed step 3 redirects back to wherever the wizard actually
  left off, rather than trusting the browser's history or a bookmarked URL.
- **Session-backed state, atomic save** — nothing is written to the
  database until the final step is confirmed. An abandoned or half-filled
  wizard never leaves a partial `Assessment` behind.
- **Isolated risk-scoring logic** (`dpia/scoring.py`) — each selected risk
  factor contributes a severity weight; each mitigation reduces its
  associated factor's contribution (floored at zero, so a mitigation can
  neutralize its own risk factor but can't discount an unrelated one). The
  totals classify the assessment as Low, Medium, or High risk, each with a
  recommendation. Pure functions, no database or view coupling — reused
  identically by the wizard's live preview and the saved assessment's
  detail/PDF view.
- **Risk factor catalog** — nine well-established DPIA screening criteria
  (evaluation/scoring, automated decision-making with a significant
  effect, systematic monitoring, sensitive data, large-scale processing,
  dataset matching, vulnerable data subjects, novel technology, processing
  that limits a data subject's rights), maintained through the Django
  admin.
- **Dashboard** — every past assessment with its status and risk level at
  a glance, risk level shown with an icon and text label (not color
  alone), so it doesn't disappear for colorblind reviewers or on a
  black-and-white printout.
- **PDF export** — the same sections the wizard walks through, in the
  same order, ready to hand to a reviewer.

## Built with

- **Backend**: Django (models, admin, session-backed multi-step wizard,
  a small `TypedDict` to keep the dashboard's per-row typing honest) —
  built with Django, not a marginally leaner alternative, to maintain a
  consistent stack across this portfolio's four projects
- **Frontend**: Django templates, plain CSS (light/dark aware, palette
  shared with Project 2) and no JavaScript — the wizard's state lives on
  the server, so a plain multi-page form is simpler and more defensible
  than reimplementing that state in the browser
- **PDF generation**: [ReportLab](https://www.reportlab.com/), matching
  Project 2's export pipeline for consistency across the portfolio
- **Tests**: Django's built-in test runner, matching Project 2 rather
  than introducing pytest for a single project in an otherwise
  consistent portfolio (`python manage.py test dpia`)
- **Configuration**: `SECRET_KEY` / `DEBUG` / `ALLOWED_HOSTS` read from
  environment variables with dev-only fallbacks (`config/settings.py`,
  `.env.example`) — the codebase is deploy-ready without code changes
- **Deployment**: [Render](https://render.com) — see **Deployment** below
  for why this project uses a persistent web service instead of Vercel's
  serverless runtime (Project 2's choice)

## Data privacy & compliance design — read before treating this as authoritative

**This is a simplified internal risk model inspired by common DPIA
practice, not an official regulatory scoring system**, and nothing this
tool outputs is legal advice.

The risk factor catalog's shape loosely follows well-known DPIA screening
criteria (the kind referenced in GDPR Art. 35 guidance and CPRA
risk-assessment practice), and the scoring thresholds
(`dpia/scoring.py`) are a deliberately simple, hand-picked model — not a
calibrated statistical one and not a citation to any specific article,
section, or agency publication. Severity weights are an internal 1-3
scale for this tool alone.

Every recommendation this tool produces, on screen or in an exported
PDF, carries the disclaimer: *"This assessment is a simulation for
portfolio/demonstration purposes and does not constitute legal advice."*

Wherever a real legal citation, threshold, or deadline would normally
belong, the source carries a
`# TODO: VERIFY exact legal citation against official source` comment
instead of a stated-as-fact figure, rather than being resolved with an
invented citation. See `dpia/models.py` and
`dpia/management/commands/seed_dpia.py` for the full list — consolidated
here for anyone auditing this repo:

| Location | What needs verification |
|---|---|
| `dpia/models.py` (`RiskFactor` docstring) | The risk factor catalog's relationship to any specific regulatory "likely high risk" checklist (e.g. GDPR Art. 35 guidance) — currently described as "loosely follows the shape of," not cited to a specific provision. |
| `dpia/management/commands/seed_dpia.py` (module docstring) | Same catalog, at the point it's actually seeded into the database. |

All company, project, and scenario details in the seed data (NimbusCart,
the AI recommendation engine proposal) are fictional, invented for this
demonstration.

## Running it locally

```bash
# 1. Clone/enter the project directory, then create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up the database
python manage.py migrate

# 4. Load the risk factor catalog and one example assessment
python manage.py seed_dpia

# 5. Create an admin login (choose your own username/password here —
#    there is no preset admin account in this repo)
python manage.py createsuperuser

# 6. Run the server
python manage.py runserver
```

By default the app runs with a development-only fallback secret key and
`DEBUG=True`, so the steps above work with zero configuration. To
override them (required before any real deployment — see **Security
notes** below), copy `.env.example` to `.env` and fill in real values,
or set `DJANGO_SECRET_KEY` / `DJANGO_DEBUG` / `DJANGO_ALLOWED_HOSTS` as
environment variables directly.

Then visit:

- **Dashboard**: <http://127.0.0.1:8000/>
- **New assessment (the wizard)**: <http://127.0.0.1:8000/assessments/new/step-1/>
- **Admin (risk factor catalog)**: <http://127.0.0.1:8000/admin/>
- **About**: <http://127.0.0.1:8000/about/>

Re-running `python manage.py seed_dpia` clears and reloads the risk
factor catalog and example assessment (pass `--keep` to add to existing
records instead).

## Testing

```bash
python manage.py test dpia
```

31 tests cover the parts most likely to break silently: the risk-scoring
function directly (`RiskScoreCalculationTests`) across zero factors, a
single low-severity factor, multiple unmitigated high-severity factors,
a mitigation reducing but not eliminating a factor's contribution, a
mitigation fully offsetting every factor, and the boundary values
between Low/Medium/High; the wizard's step-guarding, session
persistence, and final-submission behavior driven through the real
endpoints; the dashboard's risk-level display; and the PDF export
producing well-formed, section-complete, disclaimer-carrying output.

## Project structure

```
config/                          Django project settings & root URLs
dpia/                            The DPIA app
  models.py                      RiskFactor, Assessment, ProcessingDescription,
                                   NecessityProportionality, MitigationMeasure
  scoring.py                     Risk-scoring logic, isolated and unit-tested
  forms.py                       The wizard's per-step forms
  views.py                       Wizard steps, dashboard, detail, export views
  exports.py                     PDF export logic
  admin.py                       Django admin configuration
  tests.py                       Scoring, wizard-flow, view, and export tests
  templatetags/dpia_extras.py    The step-indicator inclusion tag
  management/commands/
    seed_dpia.py                  Risk factor catalog + one example DPIA for NimbusCart
  templates/dpia/                 Dashboard, about, detail, and wizard templates
static/                          CSS (shared palette with Project 2)
.env.example                     Environment variables this app reads (copy to .env)
render.yaml                      Render Blueprint (web service + Postgres)
```

## Security notes

- `SECRET_KEY`, `DEBUG`, and `ALLOWED_HOSTS` are read from environment
  variables (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`)
  with dev-only fallbacks — see `config/settings.py` and `.env.example`.
  Never commit a real `.env` file (it's already git-ignored).
- CSRF protection is on for every form, including all 5 wizard steps.
- The wizard's session data is only ever read back by server-side view
  code and validated through the same Django forms used on submission —
  a request that skips ahead or replays an old step is redirected rather
  than trusted (`_require_step` in `dpia/views.py`).
- The admin login is rate-limited (5 attempts/minute per IP) against
  brute force, the same as Project 2.
- There is no admin account bundled with this repo or its seed data —
  `createsuperuser` (step 5 above) is interactive and always asks you to
  set your own username/password.
- `db.sqlite3` is git-ignored. Seed data lives in
  `dpia/management/commands/seed_dpia.py`, not in the database file, so
  nothing sensitive is at risk of being committed.
- `pip-audit` reports no known vulnerabilities in the pinned dependency
  set as of the last review.

## Deployment (Render)

This app fits a traditional, always-on host better than a serverless
one: it holds a relational data model plus session-backed multi-step
wizard state, and while Django's database-backed sessions would work on
a serverless runtime too, a persistent Django/Postgres service keeps the
wizard's request lifecycle simple and avoids entangling it with cold
starts. Project 2 (Data-Mapping-ROPA) used Vercel — a good fit for its
simpler, mostly read-heavy dashboard — and Project 1 already flagged
Render/Railway as the natural next step for a project like this one;
this project is where that step actually gets taken.

**Option A — Blueprint (recommended):** Render → *New* → *Blueprint*,
point it at `GugaValenca/dpia-privacy-impact-assessment`. `render.yaml`
provisions the web service and a free Postgres database together,
auto-generates `DJANGO_SECRET_KEY`, and wires `DATABASE_URL` from the
database to the web service automatically.

**Option B — manual setup:**

1. **Create a Postgres database**: Render dashboard → *New* → *PostgreSQL*
   (free tier is fine for a portfolio demo). Copy its *Internal Database
   URL*.
2. **Create a web service**: *New* → *Web Service*, connect
   `GugaValenca/dpia-privacy-impact-assessment`.
   - Build command: `pip install -r requirements.txt && python manage.py migrate`
   - Start command: `gunicorn config.wsgi:application`
3. **Set environment variables** (Web Service → *Environment*):
   - `DJANGO_SECRET_KEY` — a freshly generated one (see `.env.example`
     for the one-liner that generates it)
   - `DJANGO_DEBUG` — `False`
   - `DATABASE_URL` — the Internal Database URL from step 1
   - `DJANGO_ALLOWED_HOSTS` — only needed for a custom domain; Render's
     `*.onrender.com` hostname is trusted automatically at runtime
4. **Load the risk factor catalog and create an admin login** (one-time,
   via Render's dashboard *Shell* tab on the web service):
   ```bash
   python manage.py seed_dpia
   python manage.py createsuperuser
   ```
5. **Deploy**: push to the connected branch, or trigger a manual deploy
   from the dashboard.

## About the author

Gustavo Valença is a Brazilian-trained lawyer with legal team leadership
experience, working across Python/Django development and data privacy
law (LGPD, GDPR, CCPA). This project reflects that combination directly:
a genuine DPIA workflow's judgment calls and risk criteria, modeled as a
structured, tested Django application rather than a static checklist.

This is **Project 3** of a four-project portfolio:

1. [LGPD-GDPR-CCPA-Comparative-Analysis](https://github.com/GugaValenca/lgpd-gdpr-ccpa-comparative-analysis) — comparing the underlying legal frameworks side by side.
2. [Data-Mapping-ROPA](https://github.com/GugaValenca/data-mapping-ropa) — recording processing activities already running.
3. **DPIA-Privacy-Impact-Assessment** (this project) — assessing a new one before it launches.
4. A privacy policy generator + incident-response plan tool (planned).

[![GitHub](https://img.shields.io/badge/GitHub-GugaValenca-181717?style=flat&logo=github&logoColor=white)](https://github.com/GugaValenca)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-gugavalenca-0A66C2?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/gugavalenca/)
