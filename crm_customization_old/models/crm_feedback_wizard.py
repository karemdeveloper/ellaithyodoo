from odoo import models, fields, api

class CrmFeedbackWizard(models.TransientModel):
    _name = 'crm.feedback.wizard'
    _description = 'CRM Feedback Wizard'

    date = fields.Datetime(string="Date", default=fields.Datetime.now,)
    salesperson_id = fields.Many2one('res.users', string="Salesperson")
    feedback = fields.Text(string="Feedback")
    feedback2 = fields.Selection([
        ('not_contacted', 'Not contacted'),
        ('answered', 'Answered'),
        ('no_answer', 'No answer – Phone off'),
        ('wrong_number', 'Wrong number'),
        ('callback_required', 'Callback required'),
    ], string="Feedback")
    lead_ids = fields.Many2many('crm.lead', string="Opportunities")
    next_stage_id = fields.Many2one('crm.stage', string="Next Stage")
    show_next_stage = fields.Boolean(string="Show Next Stage", compute="_compute_show_next_stage", store=False)
    
    @api.depends('lead_ids')
    def _compute_show_next_stage(self):
        """Show next stage field only if all selected opportunities are in 'New' stage"""
        for wizard in self:
            wizard.show_next_stage = False
            if wizard.lead_ids:
                # Check if all leads are in "New" stage
                # Assuming "New" stage has sequence 1 or name "New"
                new_stage = self.env['crm.stage'].search([
                    '|',
                    ('name', '=', 'New'),
                    ('sequence', '=', 1)
                ], limit=1)
                
                if new_stage:
                    all_in_new = all(lead.stage_id.id == new_stage.id for lead in wizard.lead_ids if lead.stage_id)
                    wizard.show_next_stage = all_in_new

    def action_add_feedback(self):
        """Create feedback lines for selected leads and move to next stage if specified"""
        for lead in self.lead_ids:
            self.env['crm.feedback'].create({
                'lead_id': lead.id,
                # 'date': self.date,
                'salesperson_id': self.salesperson_id.id,
                'feedback2': self.feedback2,
            })
            
            # Move to next stage if specified (only for leads in New stage)
            if self.next_stage_id and self.show_next_stage:
                lead.write({'stage_id': self.next_stage_id.id})
                
        return {'type': 'ir.actions.act_window_close'}
    ###########################################################################
    @api.model
    def default_get(self, fields_list):
        """Set default salesperson from first selected lead"""
        res = super(CrmFeedbackWizard, self).default_get(fields_list)

        # Get lead_ids from either active_ids or default_lead_ids context
        lead_ids = []

        # Check if default_lead_ids is already set (from direct context)
        if 'lead_ids' in res and res['lead_ids']:
            # Extract IDs from the Many2many command format [(6, 0, [ids])]
            if isinstance(res['lead_ids'], list) and res['lead_ids'] and isinstance(res['lead_ids'][0], tuple):
                lead_ids = res['lead_ids'][0][2] if len(res['lead_ids'][0]) > 2 else []

        # If not, get from active_ids (when called from list/tree view)
        if not lead_ids:
            lead_ids = self.env.context.get('active_ids') or []

        if lead_ids:
            leads = self.env['crm.lead'].browse(lead_ids)
            if leads:
                res['lead_ids'] = [(6, 0, leads.ids)]
                res['salesperson_id'] = leads[0].user_id.id if leads[0].user_id else False

        return res
