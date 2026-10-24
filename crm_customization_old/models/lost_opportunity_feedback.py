from odoo import models, fields, api, _


class LostOpportunityFeedback(models.Model):
    _name = 'lost.opportunity.feedback'
    _description = 'Lost Opportunity Feedback'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, 
                       default='New', tracking=True)
    review_id = fields.Many2one('lost.opportunity.review', string='Review', tracking=True)
    lead_id = fields.Many2one('crm.lead', string='Opportunity', required=True, tracking=True)
    salesperson_id = fields.Many2one(related='lead_id.user_id', string='Salesperson', 
                                     store=True, readonly=True, tracking=True)
    phone_primary = fields.Char(string='Phone',related='partner_id.phone', store=True, readonly=True, tracking=True)
    feedback = fields.Selection([
        ('valid', 'Valid'),
        ('not_valid', 'Not Valid')
    ], string='Valid/Not Valid', required=True, default='valid', tracking=True)
    description = fields.Text(string='Description', tracking=True, 
                             help='Required if feedback is Not Valid')
    date = fields.Date(string='Feedback Date', required=True, default=fields.Date.today, 
                      tracking=True)
    
    # Related fields for convenience
    lead_name = fields.Char(related='lead_id.name', string='Opportunity Name', readonly=True)
    partner_id = fields.Many2one(related='lead_id.partner_id', string='Customer', readonly=True)
    lost_reason_id = fields.Many2one(related='lead_id.lost_reason_id', string='Lost Reason', 
                                     readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed')
    ], string='Status', default='draft', required=True, tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('lost.opportunity.feedback') or 'New'
        return super(LostOpportunityFeedback, self).create(vals)

    def action_confirm(self):
        """Confirm feedback"""
        self.write({'state': 'confirmed'})

    def action_reset_to_draft(self):
        """Reset to draft"""
        self.write({'state': 'draft'})

    @api.constrains('feedback', 'description')
    def _check_description(self):
        """Ensure description is filled if feedback is not valid"""
        for record in self:
            if record.feedback == 'not_valid' and not record.description:
                from odoo.exceptions import ValidationError
                raise ValidationError(_('Description is required when feedback is "Not Valid".'))

