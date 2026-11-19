# Source provenance and rights (demo/sources)

Each source file carries its own header (URL, publisher, rights, change notice). Summary, fetched/created 2026-11-19:

| File | Origin | Rights |
| --- | --- | --- |
| pg_verifybackup, pg_checksums | PostgreSQL 18 documentation excerpts | PostgreSQL License (see POSTGRESQL_LICENSE.txt) |
| pg_upgrade, pg_continuous_archiving, pg_sql_dump | PostgreSQL 18 documentation, first 90 lines of extracted text | PostgreSQL License |
| python_venv | docs.python.org tutorial "Virtual Environments and Packages" | Python Software Foundation License for the documentation, https://docs.python.org/3/license.html. Copyright (c) Python Software Foundation. |
| ready_power_outages, ready_floods, ready_home_fires | FEMA Ready.gov pages | US federal government work; FEMA states most material is free of copyright (https://www.fema.gov/about/website-information). No endorsement by FEMA/DHS is implied. |
| original_release_check_sop | written for this demo | MIT, like this repository |

The 7 fetched files are excerpts (first 90 lines at most, whitespace collapsed, one sentence per line, headings and
navigation removed). Rebuild them with `python demo/tools/build_sources.py` (needs network and beautifulsoup4);
the live pages may have changed since the capture date.
