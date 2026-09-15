Incremental changes on top of `database/schema/` (schema v2). Files are applied in name order by
`scripts/validate_system.py` on every start and recorded in `schema_migrations`.
Schema v1 and its migrations are archived in `../schema_v1_archive` and `../migrations_v1_archive`.
