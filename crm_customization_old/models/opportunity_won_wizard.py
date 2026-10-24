from odoo import models, fields, api


class OpportunityWonWizard(models.TransientModel):
    _name = 'opportunity.won.wizard'
    _description = 'Mark Opportunity as Won'

    chassis_number = fields.Char(string='Chassis/Serial Number', required=True)
    sale_order_id = fields.Char(string='Sales Order', required=True)
    lead_id = fields.Many2one('crm.lead', string='Opportunity')

    @api.model
    def default_get(self, fields_list):
        """Pre-fill lead_id from context"""
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            res['lead_id'] = self.env.context.get('active_id')
        return res

    def action_confirm(self):
        """Save chassis number and sales order to opportunity and mark as won"""
        self.ensure_one()
        if self.lead_id:
            self.lead_id.write({
                'chassis_number': self.chassis_number,
                'sale_order_id': self.sale_order_id,
            })
            # Mark as won
        self.lead_id.with_context(from_won_wizard=True).action_set_won_rainbowman()        
        return {'type': 'ir.actions.act_window_close'}

