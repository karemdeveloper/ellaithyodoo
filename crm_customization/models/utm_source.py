from odoo import models


class UtmSource(models.Model):
    _inherit = "utm.source"

    def unlink(self):
        """Delete standard Odoo UTM sources safely.

        Ellaithy CRM uses ``res.source`` through ``crm.lead.source_name``.
        The native ``crm.lead.source_id`` is retained only for Odoo/UTM
        compatibility. During module updates Odoo can remove UTM source records;
        PostgreSQL refuses that deletion if a lead still references the source.
        Clear those native references before deleting the UTM source. This does
        not alter Ellaithy's Customer Source.
        """
        source_ids = self.ids
        if source_ids:
            leads = self.env["crm.lead"].sudo().with_context(active_test=False).search([
                ("source_id", "in", source_ids),
            ])
            if leads:
                leads.write({"source_id": False})
        return super().unlink()
