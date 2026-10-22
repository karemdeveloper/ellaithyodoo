# CRM Source FK Fix v18.0.0.4.0

- Ellaithy business source remains `res.partner.crm_source_id -> res.source -> crm.lead.source_name`.
- Odoo native `crm.lead.source_id -> utm.source` is kept only for standard CRM/marketing compatibility.
- `crm_lead_source_id_fkey` is repaired during model initialization to `ON DELETE SET NULL`.
- A defensive `utm.source.unlink()` override also clears legacy references before deletion.
- Native field label is `Odoo Marketing Source` to avoid confusion with Ellaithy's Customer Source.
