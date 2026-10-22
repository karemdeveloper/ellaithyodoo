# Create Opportunity Non-Blocking v4

Based on Fast Create v3.

Changes:
- Opportunity lead creation remains synchronous and immediate.
- Partner salesperson synchronization is queued and processed every minute by cron.
- Round-robin selection no longer updates a shared pointer in the user's transaction.
- Round-robin uses an atomic counter in a short independent DB transaction.
- The round-robin counter has a 300ms DB lock timeout and a non-blocking fallback.
- No source/FK behavior changes.

Goal: a slow partner write or a stuck round-robin pointer must not hold the Create Opportunity popup for minutes.
