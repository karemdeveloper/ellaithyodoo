# Always Fast v5

Built from the proven Fast Create v3.

The interactive Create Opportunity request now performs no shared-state writes
apart from inserting the crm.lead itself.

Changes:
- stateless salesperson selection: reads branch/team/shift sequences but does not
  update ir.config_parameter or any round-robin pointer;
- no res.partner.write() in the button request;
- wizard Opportunity Name is passed directly to crm.lead, bypassing the separate
  _generate_lead_name() sequence path;
- mail/chatter tracking is disabled for this technical create request;
- safe custom Source handling from Fast Create v3 is retained;
- existing central one-open-opportunity validation remains in crm.lead.create().

There are no new models, tables, crons or schema dependencies in this ZIP.
