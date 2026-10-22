# Create Opportunity Performance Fix

Version: 18.0.0.2.0

Changes:
- Pre-fills opportunity wizard defaults directly from the customer action context.
- Removes duplicate open-opportunity queries during wizard save.
- Uses a single indexed-style search with limit=1 for the open opportunity validation.
- Reuses the shared distribute.sequence round-robin implementation.
- Replaces ir.config_parameter get_param/set_param round-robin pointer access with transactional SQL and PostgreSQL advisory locking, avoiding registry/config cache invalidation on every new opportunity.
- Preserves concurrency safety for salesperson round-robin assignments.
- Removes debug print calls from crm.lead.create().
- Adds a timing log entry for opportunity creation.

Business rules preserved:
- Create CRM permission remains required.
- One open opportunity per customer remains enforced unless the user has the bypass group.
- Existing active customer salesperson is reused.
- Archived salesperson falls back to distribution.
- Branch/shift round-robin behavior is preserved.
