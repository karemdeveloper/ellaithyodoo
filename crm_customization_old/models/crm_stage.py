from odoo import models, fields, api

class CrmStage(models.Model):
    _inherit = 'crm.stage'

    is_lost = fields.Boolean(string="Is Lost")

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def action_set_lost(self, lost_reason_id=False):
        """Mark the lead as lost but don't archive it"""
        lost_stage = self.env['crm.stage'].search([('is_lost', '=', True)], limit=1)
        if not lost_stage:
            raise ValueError("⚠️ مفيش stage فيها is_lost=True، أضف واحدة من إعدادات CRM.")

        for lead in self:
            lead.sudo().with_context(skip_note_wizard=True).write({
                'lost_reason_id': lost_reason_id or False,
                'date_closed': fields.Datetime.now(),
                'ibs_closed_at': fields.Datetime.now(),
                'stage_id': lost_stage.id,
                'active': True,
            })
        return True