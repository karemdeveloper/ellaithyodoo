# Always Fast v5.1 — restore original naming and creator log

Based on Always Fast v5.

Restored:
- Opportunity name is no longer taken from the popup/customer text.
- `crm.lead.create()` again executes the original `_generate_lead_name(branch_id)`
  naming logic exactly as before v5.
- Normal Odoo mail/thread tracking is enabled again during lead creation so the
  creator/audit chatter entry is saved.

Still kept from v5:
- stateless/read-only salesperson assignment;
- no round-robin pointer write;
- no `res.partner.write()` in the interactive request;
- safe custom Source context handling;
- fast central open-opportunity validation.

No new models, tables, cron jobs, or schema changes.
