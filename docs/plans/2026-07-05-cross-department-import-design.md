# Cross-Department Import & Project Filter — Design

**Date:** 2026-07-05

## Problem

Runs targeting dept 77 find relevant articles in other departments (e.g. Amazon Rhône 69). Current behavior skips them (`wrong_department`) — no project created despite LLM relevance. Users also cannot filter the projects table by department.

## Decisions (brainstorming)

| Topic | Choice |
|-------|--------|
| Cross-dept articles | Import with **extracted** department, not skip |
| Run stats | **Excluded** from `articles_found` / `projects_new` / `projects_updated` |
| SSE event | Dedicated `project_imported_cross_department` |
| Project table filter | **Multi-select** departments, **server-side** via API |
| UI component | Reuse `DepartmentCombobox` (shadcn) |

## Pipeline

When `extracted_department ≠ target_department` (both set):

1. Set `extraction.department = extracted_department`
2. Continue normal flow: relevance check → company resolution → `upsert_project`
3. `mark_url_seen(url, "cross_department")`
4. Emit `project_imported_cross_department` (not `project_found`)
5. Do **not** increment run stats

When `department=null` from LLM → unchanged fallback via `ensure_department(..., search_dept)`.

## API

`GET /api/projects?departments=77&departments=69&country=FR`

- Normalizes codes to `"XX - Name"` format
- Filters `Project.department IN (...)`
- Keeps existing single `department` param for backward compatibility

## Frontend

- **Live run panel:** new status `cross_department` — blue check, label « importé → 69 »
- **Project list:** `DepartmentCombobox` above table; reload on selection change via `getProjects({ departments, country })`

## Out of scope

- Widening Exa geographic search
- URL backfill for historical `wrong_department` ProcessedUrl entries
- Persisting filter in URL/localStorage
