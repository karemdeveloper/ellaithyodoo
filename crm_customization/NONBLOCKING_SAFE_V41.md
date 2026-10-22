# Non-blocking Safe v4.1

Built from the proven Fast Create v3.

No new models, tables, queues, or cron jobs are introduced.

Changes:
- partner salesperson synchronization is best-effort with a 250ms PostgreSQL lock timeout;
- a locked customer row can no longer block/fail opportunity creation;
- round-robin pointer update is best-effort with a 250ms lock timeout;
- if the shared pointer is busy, the opportunity is still created and returned;
- all Fast Create v3 popup/source/performance fixes are retained.

This version is designed to work after a normal code restart and does not
depend on a newly-created queue model.
