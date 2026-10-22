# Create Opportunity fast save v3

Based on the user-supplied working crm_customization module.

Changes are limited to the customer -> Create Opportunity popup/save path:
- safe popup defaults (custom res.source never leaks into native utm.source);
- no duplicate open-opportunity query in the wizard;
- shared round-robin helper instead of the duplicated wizard implementation;
- round-robin pointer reads/writes use direct SQL instead of ir.config_parameter set_param cache invalidation;
- partner salesperson synchronization happens after lead creation with chatter tracking disabled;
- crm.lead open-opportunity check stops after the first match;
- timing logs identify salesperson selection, crm.lead.create, partner sync, and total request time.

No FK/schema changes. No complaint logic changes.
