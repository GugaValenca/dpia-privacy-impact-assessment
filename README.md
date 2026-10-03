# DPIA-Privacy-Impact-Assessment

[![Live Demo](https://img.shields.io/badge/Live_Demo-dpia--privacy--impact--assessment.vercel.app-000000?style=flat&logo=vercel&logoColor=white)](https://dpia-privacy-impact-assessment.vercel.app)
[![GitHub](https://img.shields.io/badge/GitHub-GugaValenca-181717?style=flat&logo=github&logoColor=white)](https://github.com/GugaValenca)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-gugavalenca-0A66C2?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/gugavalenca/)

A guided Data Protection Impact Assessment (DPIA) tool: a 5-step wizard
walks through describing a proposed processing activity, judging its
necessity and proportionality, flagging applicable risk factors, and
documenting mitigations — ending in a calculated risk score, a
recommendation, and an exportable, audit-structured PDF report.

Where [Data-Mapping-ROPA](https://github.com/GugaValenca/data-mapping-ropa)
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
  built with Django, not a marginally leaner alternative, to keep the same stack as the other three tools
- **Frontend**: Django templates, plain CSS (light/dark aware, palette
  shared with Data-Mapping-ROPA) and no JavaScript — the wizard's state lives on
  the server, so a plain multi-page form is simpler and more defensible
  than reimplementing that state in the browser
- **PDF generation**: [ReportLab](https://www.reportlab.com/), matching
  Data-Mapping-ROPA's export pipeline for consistency across the related tools
- **Tests**: Django's built-in test runner, matching Data-Mapping-ROPA rather
  than introducing pytest for a single app in an otherwise consistent
  set of tools (`python manage.py test dpia`)
- **Configuration**: `SECRET_KEY` / `DEBUG` / `ALLOWED_HOSTS` read from
  environment variables with dev-only fallbacks (`config/settings.py`,
  `.env.example`) — the codebase is deploy-ready without code changes
- **Deployment**: [Vercel](https://vercel.com) (Python/WSGI runtime),
  Postgres in production via `dj-database-url` (SQLite locally, no
  config needed), static files served by
  [WhiteNoise](https://whitenoise.readthedocs.io/) — same setup as
  Data-Mapping-ROPA, for one consistent deployment story across the related tools;
  see **Deployment** below

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
demonstration purposes and does not constitute legal advice."*

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

**Verified 2026-10-02** (live web research, not from training data): the
nine-entry structure genuinely matches the Article 29 Working Party's
WP248 rev.01 "likely high risk" criteria (endorsed by the EDPB,
interpreting GDPR Art. 35(1) — confirmed against eur-lex.europa.eu and
ico.org.uk's public summary), and the CPPA's CCPA/CPRA risk-assessment
regulations are finalized and in force as of 2026-01-01 (OAL approval
2025-09-23). This confirms the characterization above is accurate, not
overstated — the catalog still doesn't cite any specific article, section,
or agency publication as authority for an individual entry, and that
remains the deliberate design, not an unresolved gap. See the verification
comments added at each location above for sources.

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
api/index.py                   WSGI entrypoint Vercel's Python runtime routes into
vercel.json                     Vercel build/route config
config/                        Django project settings & root URLs
dpia/                           The DPIA app
  models.py                     RiskFactor, Assessment, ProcessingDescription,
                                  NecessityProportionality, MitigationMeasure
  scoring.py                    Risk-scoring logic, isolated and unit-tested
  forms.py                      The wizard's per-step forms
  views.py                      Wizard steps, dashboard, detail, export views
  exports.py                    PDF export logic
  admin.py                      Django admin configuration
  tests.py                      Scoring, wizard-flow, view, and export tests
  templatetags/dpia_extras.py   The step-indicator inclusion tag
  management/commands/
    seed_dpia.py                 Risk factor catalog + one example DPIA for NimbusCart
  templates/dpia/                Dashboard, about, detail, and wizard templates
static/                          CSS (shared palette with Data-Mapping-ROPA)
.env.example                     Environment variables this app reads (copy to .env)
```

## Security notes

- `SECRET_KEY`, `DEBUG`, and `ALLOWED_HOSTS` are read from environment
  variables (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`)
  with dev-only fallbacks — see `config/settings.py` and `.env.example`.
  Never commit a real `.env` file (it's already git-ignored). Because this
  repo is public, the fallback key is public too, so the app **refuses to
  start** with `DJANGO_DEBUG=False` unless `DJANGO_SECRET_KEY` is set,
  rather than silently serving production traffic signed with it.
- CSRF protection is on for every form, including all 5 wizard steps.
- The wizard's session data is only ever read back by server-side view
  code and validated through the same Django forms used on submission —
  a request that skips ahead or replays an old step is redirected rather
  than trusted (`_require_step` in `dpia/views.py`).
- PDF export and the admin login both accept requests from anonymous
  visitors, so each is rate-limited per visitor (`dpia/views.py`,
  `dpia/admin.py`) — 10/min for PDF export (ReportLab rendering isn't
  free), 5/min for admin login attempts. The limiter key trusts Vercel's
  `X-Real-IP` header only when actually running on Vercel
  (`RUNNING_ON_VERCEL`, `dpia/throttling.py`); elsewhere a client could
  set that header to anything, so `REMOTE_ADDR` is used instead.
- There is no admin account bundled with this repo or its seed data —
  `createsuperuser` (step 5 above) is interactive and always asks you to
  set your own username/password.
- `db.sqlite3` is git-ignored. Seed data lives in
  `dpia/management/commands/seed_dpia.py`, not in the database file, so
  nothing sensitive is at risk of being committed.
- `pip-audit` reports no known vulnerabilities in the pinned dependency
  set as of the last review.

## Deployment (Vercel)

The app is set up to deploy on Vercel's Python runtime — `vercel.json` +
`api/index.py` route every request into the Django WSGI app, and
`config/settings.py` switches from SQLite to Postgres automatically
whenever a `DATABASE_URL`/`POSTGRES_URL` is present, with no code
changes needed between the two — the same setup as Data-Mapping-ROPA, kept
deliberately identical so both projects deploy the same way.

Vercel's serverless functions have no persistent disk, which is the one
thing that actually forces a change from local dev: SQLite's on-disk
file wouldn't survive between requests there, so production needs a real
Postgres database. The DPIA wizard's multi-step state lives in Django's
database-backed session store (the default engine), so it survives
across serverless invocations the same way any other model data does —
no extra handling needed for that beyond having Postgres configured.

1. **Connect the repo**: in the Vercel dashboard, *Add New… → Project*,
   import `GugaValenca/dpia-privacy-impact-assessment` from GitHub.
2. **Add a Postgres database**: Project → *Storage* tab → *Create
   Database* → Postgres (this provisions a Neon-backed instance and
   injects `POSTGRES_URL` into the project's environment variables
   automatically — nothing to copy by hand).
3. **Set the remaining environment variables** (Project → *Settings →
   Environment Variables*):
   - `DJANGO_SECRET_KEY` — a freshly generated one (see `.env.example`
     for the one-liner that generates it)
   - `DJANGO_DEBUG` — `False`
   - `DJANGO_ALLOWED_HOSTS` — only needed for a custom domain; the
     `*.vercel.app` preview/production URL is trusted automatically
4. **Run migrations against the production database** (one-time, and
   again after any future model change — Vercel's build step doesn't run
   this for you):
   ```bash
   DATABASE_URL="<value from Vercel's Storage tab>" python manage.py migrate
   DATABASE_URL="<same value>" python manage.py createcachetable   # rate-limit counters
   DATABASE_URL="<same value>" python manage.py seed_dpia   # optional, sample data
   DATABASE_URL="<same value>" python manage.py createsuperuser
   ```
5. **Deploy**: `vercel --prod`, or push to the connected branch.

Live at [dpia-privacy-impact-assessment.vercel.app](https://dpia-privacy-impact-assessment.vercel.app) —
a Neon Postgres database provisioned through Vercel's marketplace
integration, migrated and seeded, with the full 5-step wizard verified
end to end against the live deployment (not just against the code
reading right) before being written up here.

## About the author

Gustavo Valença is a Brazilian-trained lawyer with legal team leadership
experience, working across Python/Django development and data privacy
law (LGPD, GDPR, CCPA). This project reflects that combination directly:
a genuine DPIA workflow's judgment calls and risk criteria, modeled as a
structured, tested Django application rather than a static checklist.

This is one of four related privacy tools built around the same fictional company:

1. [LGPD-GDPR-CCPA-Comparative-Analysis](https://github.com/GugaValenca/lgpd-gdpr-ccpa-comparative-analysis) — comparing the underlying legal frameworks side by side.
2. [Data-Mapping-ROPA](https://github.com/GugaValenca/data-mapping-ropa) — recording processing activities already running.
3. **DPIA-Privacy-Impact-Assessment** (this project) — assessing a new one before it launches.
4. [Incident-Breach-Response](https://github.com/GugaValenca/incident-breach-response) — responding when something goes wrong.

[![GitHub](https://img.shields.io/badge/GitHub-GugaValenca-181717?style=flat&logo=github&logoColor=white)](https://github.com/GugaValenca)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-gugavalenca-0A66C2?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/gugavalenca/)
