# PAEP Student Data Pipeline — Final

An extended multi-source ETL pipeline for the PAEP Data Engineering course.
It starts from the latest clean `main` of the original project and adds:

- MongoDB as a supplemental input source.
- [JSONPlaceholder `/users`](https://jsonplaceholder.typicode.com/users) as a
  simple public web API source.
- One consolidated output collection in MongoDB, while retaining CSV outputs
  for easy inspection and rejected-record auditing.

The original repository is not modified by this project. Its history is kept as
the read-only `upstream` remote; push to that remote is disabled.

## Pipeline flow

```text
CSV -----------+
Academic API --+--> validate --> clean --> core inner join ----+
SQLite --------+                                             |
                                                             +--> transform
MongoDB -------+--> validate --> clean --> optional left join |    + validate
Web API -------+--> normalize --> validate --> clean ---------+         |
                                                                       +--> CSV
                                                                       +--> MongoDB
```

The three academic sources remain mandatory and use the original one-to-one
inner join. MongoDB and the public web API are compatible after normalization,
so they reuse the same validation and cleaning pipeline. They are left-joined
as enrichment sources: a missing optional profile never removes an otherwise
valid academic student.

## Sources

| Source | Purpose | Key fields | Expected rows |
| --- | --- | --- | ---: |
| CSV | Identity | `student_id`, name, age, major, city | 14 raw |
| Local REST API | Academic status | `student_id`, GPA, attendance, status | 13 raw |
| SQLite | Enrollment | `student_id`, course, score | 12 joined |
| MongoDB | Student profile | `student_id`, advisor, scholarship | 12 seeded |
| JSONPlaceholder | Web-directory demo | normalized `student_id`, `web_*`, company | 10 |

JSONPlaceholder IDs `1..10` are mapped to student IDs `1001..1010` using the
configurable `student_id_offset=1000`. Its schema does not pretend to be an
academic schema: it has a small adapter that produces namespaced `web_*`
columns. This is intentionally a JSON web API rather than brittle HTML scraping,
matching the requested low-complexity learning example.

## Final dataset

The canonical run still produces 8 valid academic students and 6 rejected
records. With both enrichments enabled, the final dataset has 24 columns:

- 12 original academic columns.
- MongoDB: `advisor_name`, `scholarship_status`.
- Web API: `web_name`, `web_username`, `web_email`, `web_phone`,
  `web_website`, `web_city`, `company_name`.
- Derived/metadata: `performance_level`, `attendance_status`, `source`.

Students `1011` and `1012` have null `web_*` fields because the demonstration
API has only ten users. They remain in the dataset by design. The same final
snapshot is written to:

- `data/processed/final_dataset.csv`
- MongoDB collection `paep_student_pipeline.final_students`

Rejected source records remain in `data/rejected/rejected_records.csv` with an
explicit source, stage, and reason.

## Quick start

Requirements: Python 3.12+ and either Docker or an existing MongoDB instance.

1. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

2. Start MongoDB and seed the input collection:

   ```bash
   docker compose up -d mongodb
   python scripts/seed_mongodb.py
   ```

3. Start the existing academic mock API in one terminal:

   ```bash
   python mock_api/server.py
   ```

4. Run the pipeline in another terminal:

   ```bash
   python main.py
   ```

5. Inspect the single MongoDB dataset:

   ```bash
   mongosh "mongodb://localhost:27017/paep_student_pipeline" \
     --eval "db.final_students.find().sort({student_id: 1}).pretty()"
   ```

6. Run the offline test suite:

   ```bash
   python -m pytest -q
   ```

The tests use local HTTP fixtures and in-memory fakes for MongoDB, so they do
not need internet access or a running MongoDB server.

## Configuration

All extensions are controlled in `config.json`:

```json
{
  "sources": {
    "mongodb": {
      "enabled": true,
      "uri": "mongodb://localhost:27017",
      "uri_env": "MONGODB_URI",
      "database": "paep_student_pipeline",
      "collection": "student_profiles"
    },
    "web": {
      "enabled": true,
      "url": "https://jsonplaceholder.typicode.com/users",
      "timeout_seconds": 10,
      "student_id_offset": 1000
    }
  },
  "output": {
    "mongodb": {
      "enabled": true,
      "uri": "mongodb://localhost:27017",
      "uri_env": "MONGODB_URI",
      "database": "paep_student_pipeline",
      "collection": "final_students"
    }
  }
}
```

Set `MONGODB_URI` to override the URI without committing credentials. Each new
section is optional for backward compatibility: configurations from the
original project still run the original CSV/API/SQLite-to-CSV flow.

## Design decisions

- All five input classes implement `BaseSource.extract() -> DataFrame`.
- MongoDB and web records pass through the existing source validation and
  cleaning functions after source-specific extraction/normalization.
- Supplemental fields are namespaced or checked for collisions, so a source
  cannot silently overwrite a core academic field.
- Duplicate supplemental IDs and incompatible IDs are rejected before merging.
- Supplemental values are included in incremental fingerprints. Changing an
  advisor, scholarship, email, or company reprocesses that student.
- The MongoDB destination is replaced with the complete validated snapshot on
  each successful run and has a unique index on `student_id`, preventing stale
  documents from surviving.
- CSV/state consistency from the original incremental pipeline is preserved.
  MongoDB loading happens after the state is committed, so an unavailable
  destination can be retried on the next unchanged run without corrupting the
  reusable snapshot.

## Project structure

```text
app/
  sources/
    mongodb_source.py       # MongoDB input adapter
    web_api_source.py       # JSONPlaceholder normalization adapter
  output/
    mongodb_writer.py       # complete final collection loader
  transformation/
    integration.py          # original core join + optional enrichment join
data/raw/
  mongodb_students.json     # reproducible MongoDB source seed
scripts/
  seed_mongodb.py
compose.yaml
config.json
main.py
tests/
```

The original data contract and project plan remain in `DATA_CONTRACT.md` and
`PROJECT_PLAN.md`; the extension contract is appended to `DATA_CONTRACT.md`.
