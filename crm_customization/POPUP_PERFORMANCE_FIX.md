# Create Opportunity popup performance fix

This build is based on the supplied working `crm_customization` module.

Only the Create Opportunity popup path was optimized:

- `res.partner.action_open_create_opportunity_wizard()` passes partner defaults in the action context.
- `opportunity.wizard.default_get()` uses those defaults and only reads the partner as a compatibility fallback.
- `opportunity.wizard._get_next_salesperson()` delegates to the existing shared `distribute.sequence` round-robin helper.
- The duplicate open-opportunity query was removed from the wizard. `crm.lead.create()` remains the single enforcement point.
- Removed unsupported `tracking=True` from the transient wizard selection field.

No source/FK model logic was added or changed.
