# Pin a row lock with a statement spy; a race test under SQLite cannot see FOR UPDATE

Date: 2026-10-13   Area: test

**Context**: `section_review_service._write_label` reads the reader's row `FOR UPDATE` so two labels
pressed within milliseconds apply in turn on PostgreSQL (the waiter re-reads the updated row under
READ COMMITTED). The suite runs on SQLite, where SQLAlchemy renders `with_for_update()` as nothing,
so the race test that exercised two writes passed with the lock and without it: the mutant that
dropped `with_for_update` survived every behavioural test.

**Rule**: when a correctness property lives in a clause the test database does not honour
(`FOR UPDATE`, `lock_timeout`, an isolation level), pin the clause itself: spy on the ORM call that
emits it (`sqlalchemy.orm.Query.with_for_update`, recording the entity it was applied to) or compile
the statement with the PostgreSQL dialect and assert the SQL, and assert the read path does NOT
take it. Keep the behavioural race test beside it for what SQLite can show (the second write lands
on the first's row), and say in the test's docstring which half SQLite cannot see. The same shape
holds for a dropped commit after a SAVEPOINT (`test-sqlite-savepoint-release-hides-a-dropped-commit.md`).

**Evidence**: `backend/tests/unit/test_section_review_service.py::test_a_write_reads_its_row_for_update_and_a_read_does_not`
(the spy records `section_reviews` once for `set_label` and nothing for `review_state`; the
no-lock mutant fails it) beside `test_two_first_labels_racing_on_the_insert_both_land`.
