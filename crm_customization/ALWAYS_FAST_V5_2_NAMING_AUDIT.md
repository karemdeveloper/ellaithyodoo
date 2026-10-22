# Always Fast v5.2 — original naming + lightweight creator audit

Goal: preserve the performance characteristics of v5 while restoring the two
business behaviors requested by the user.

Kept from v5:
- stateless/read-only salesperson assignment;
- no round-robin pointer write;
- no res.partner.write() during the interactive request;
- safe custom Source context;
- mail/thread tracking disabled during crm.lead.create() for speed.

Restored:
- original crm_lead_sequence naming path via _generate_lead_name(branch_id);
- creator visibility in chatter through one lightweight mail.message.

Additional diagnostics:
- logs timing of the original name generator separately;
- logs timing of the lightweight creator audit message.

No new models, tables, cron jobs or schema changes.
