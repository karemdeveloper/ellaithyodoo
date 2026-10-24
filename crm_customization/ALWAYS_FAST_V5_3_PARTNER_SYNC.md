# Always Fast v5.3 - Customer Salesperson Sync

This build is based on Always Fast v5.2.

Changes:
- Keeps the fast/stateless Create Opportunity flow.
- Preserves original opportunity sequence naming.
- Preserves the lightweight creator audit message.
- After creating an opportunity, synchronizes `crm.lead.user_id` to the linked customer's `res.partner.user_id`.
- Customer sync runs with mail/thread tracking disabled and is timing-logged.
- A sync failure does not cancel an already-created opportunity.

Expected log line:
`Create Opportunity timing: partner salesperson sync 0.00Xs`
