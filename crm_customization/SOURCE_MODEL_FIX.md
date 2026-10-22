# CRM source model hardening (18.0.0.3.0)

Ellaithy business source data stays on `res.source`:

- Customer: `res.partner.crm_source_id`
- Opportunity: `crm.lead.source_name`
- Create Opportunity wizard: `opportunity.wizard.source_id`

Odoo's native `crm.lead.source_id` -> `utm.source` remains available for standard
Odoo/UTM compatibility but is not used by the Ellaithy Create Opportunity flow.

The module now inherits `utm.source.unlink()` and clears native CRM lead references
before a UTM source is deleted. This prevents `crm_lead_source_id_fkey` validation
errors during module upgrades or UTM cleanup while preserving Ellaithy's custom source.

The custom fields are labelled `Customer Source` to remove the ambiguous duplicate
`Source` label warning in CRM.
