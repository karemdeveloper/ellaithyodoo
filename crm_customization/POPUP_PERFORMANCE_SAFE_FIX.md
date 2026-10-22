# Safe Create Opportunity popup optimization

Base: the user-supplied working crm_customization module.

Only the popup path was changed:
- preload partner/name/area/branch values in the popup action;
- use `ellaithy_popup_source_id` for the custom `res.source`;
- NEVER pass `default_source_id` from the popup, because crm.lead.source_id is Odoo's native `utm.source`;
- explicitly strip `default_source_id` before creating crm.lead;
- use a fast search_count existence check instead of loading all historical opportunities;
- remove unsupported tracking=True from the transient wizard selection.

No FK/schema changes. No `utm.source.unlink()` override. No complaint/source model changes.
