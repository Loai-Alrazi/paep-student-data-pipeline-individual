# PAEP Student Data Pipeline - Individual Extension

This repository is an individual extension of the original PAEP team project.
It preserves the team project's Git history and adds MongoDB input/output and
real HTML web scraping without changing the original repository.

## Project Origin

This project is built on the team repository `paep-student-data-pipeline`.
The original team history is preserved in this repository; commit `e39354c`
remains an ancestor of the current branch. The configured `upstream` remote is
read-only for this work and its push URL is disabled.

The team baseline already provided:

- CSV student identity data.
- A local REST API with academic data.
- SQLite enrollment data.
- Source validation, cleaning, integration, transformation, lineage, metrics,
  rejected-record output, and incremental processing.
- The canonical CSV output at `data/processed/final_dataset.csv`.

The individual extension adds:

- MongoDB collection `student_profiles` as an optional student enrichment
  source.
- A real Web Scraping source using `requests` and `BeautifulSoup` against the
  educational site `https://quotes.toscrape.com/`.
- MongoDB collection `final_students` as a destination for the complete final
  student snapshot.
- Docker Compose setup, a reproducible MongoDB seed, and isolated tests for the
  new behavior.

## Sources and Outputs

| Component | Role | Relationship |
| --- | --- | --- |
| CSV | Student identity and demographics | Core student source |
| Local REST API | GPA, attendance, and status | Core join on `student_id` |
| SQLite | Courses and enrollments | Core join on `student_id` |
| MongoDB `student_profiles` | Advisor and scholarship fields | Optional LEFT JOIN on `student_id` |
| Quotes to Scrape HTML | Quotes, authors, and tags | Independent scraped dataset |

JSONPlaceholder is not used. It was removed because it is a REST API rather
than Web Scraping, and mapping its IDs to student IDs would not represent a
real relationship.

The project writes:

- `data/processed/final_dataset.csv`: the unified student dataset.
- `paep_student_pipeline.final_students`: the same student snapshot in
  MongoDB.
- `data/processed/scraped_quotes.csv`: the independent Web Scraping result.
- `data/rejected/rejected_records.csv`: rejected student-source records.

## Architecture and Data Flow

```text
Student pipeline

CSV -----------+
REST API ------+--> Validate --> Clean --> INNER JOIN --+
SQLite --------+                                        |
                                                        +--> Transform
MongoDB -------------> Validate --> Clean --> LEFT JOIN |    --> Validate
                                                             --> CSV
                                                             --> MongoDB

Independent Web Scraping pipeline

HTML page --> requests --> BeautifulSoup --> Validate --> Clean
          --> Transform --> scraped_quotes.csv
```

The student pipeline only integrates sources with a real `student_id`
relationship. The MongoDB LEFT JOIN cannot remove a valid core student when a
profile is absent. Scraped quotes have no natural student key, so they are
processed separately and never receive an invented mapping.

All extractors implement the small `BaseSource.extract() -> DataFrame`
contract. The orchestration remains synchronous and intentionally simple for
an academic demonstration.

## MongoDB Design

MongoDB has two separate responsibilities and collections:

- Input: `paep_student_pipeline.student_profiles`
- Output: `paep_student_pipeline.final_students`

The source fixture is tracked at `data/raw/mongodb_students.json` and seeded by
`scripts/seed_mongodb.py`. The final writer replaces the destination snapshot
on every run, creates a unique `student_id` index, and rejects duplicate IDs
before connecting. Repeated runs therefore do not retain old documents.

`MONGODB_URI` can override the local default. No credentials are stored in the
repository. Configuration validation also rejects using the same collection
for both input and output.

## Web Scraping Design

`app/sources/web_scraping_source.py` performs a real HTTP GET and parses
`div.quote`, `span.text`, `small.author`, and `a.tag` HTML elements with
BeautifulSoup. It does not use Selenium, authentication, protection bypasses,
or hidden APIs.

The independent dataset follows these stages:

1. Extract quote text, author, tags, and source URL from HTML.
2. Validate its schema and required text values.
3. Clean whitespace and remove repeated quote/author pairs.
4. Transform it by adding `tag_count` and `quote_length`.

Tests use local HTML strings and request mocks, so the automated suite does not
depend on the public website.

## Configuration

The extension settings in `config.json` are:

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
    "web_scraping": {
      "enabled": true,
      "url": "https://quotes.toscrape.com/",
      "timeout_seconds": 10
    }
  },
  "output": {
    "scraped_quotes": "data/processed/scraped_quotes.csv",
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

Optional extension sections can be disabled for an offline baseline run. When
Web Scraping is enabled, the pipeline needs internet access for the configured
HTML page. The core REST API remains local.

## Running the Project

Requirements: Python 3.12+, Docker Desktop (or another MongoDB instance), and
internet access for the one-page scraping example.

1. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

2. Start MongoDB and seed its source collection:

   ```bash
   docker compose up -d mongodb
   python scripts/seed_mongodb.py
   ```

3. Start the existing academic API in one terminal:

   ```bash
   python mock_api/server.py
   ```

4. Run the pipeline in another terminal:

   ```bash
   python main.py
   ```

5. Inspect MongoDB:

   ```bash
   mongosh "mongodb://localhost:27017/paep_student_pipeline" --eval "db.student_profiles.countDocuments(); db.final_students.countDocuments(); db.final_students.find().sort({student_id: 1}).pretty()"
   ```

6. Run the test suite:

   ```bash
   python -m pytest -q
   ```

The automated tests mock MongoDB and public HTTP access. A real end-to-end
MongoDB check additionally requires a running Docker Engine.

## Project Structure

```text
app/
  sources/
    csv_source.py
    api_source.py
    database_source.py
    mongodb_source.py
    web_scraping_source.py
  transformation/
    integration.py
    web_scraping.py
  output/
    csv_writer.py
    mongodb_writer.py
data/raw/mongodb_students.json
scripts/seed_mongodb.py
compose.yaml
config.json
main.py
tests/
```

See `DATA_CONTRACT.md` for the exact schemas and validation rules.
