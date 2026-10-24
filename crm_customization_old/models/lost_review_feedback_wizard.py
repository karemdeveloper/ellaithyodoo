from odoo import models, fields, api, _
from odoo.exceptions import UserError


class LostReviewFeedbackWizard(models.TransientModel):
    _name = 'lost.review.feedback.wizard'
    _description = 'Create Feedback from Lost Review'

    review_id = fields.Many2one('lost.opportunity.review', string='Review', required=True)
    line_ids = fields.Many2many('lost.opportunity.review.line', string='Selected Lines')
    feedback_line_ids = fields.One2many('lost.review.feedback.wizard.line', 'wizard_id', 
                                        string='Feedback Lines')

    @api.model
    def default_get(self, fields_list):
        """Pre-fill lines from context"""
        res = super().default_get(fields_list)
        
        # Get review_id from context
        review_id = self.env.context.get('default_review_id')
        if review_id:
            res['review_id'] = review_id
        
        # Get selected line IDs from context
        selected_line_ids = self.env.context.get('selected_line_ids', [])
        if selected_line_ids:
            lines = self.env['lost.opportunity.review.line'].browse(selected_line_ids)
            
            feedback_lines = []
            for line in lines:
                if line.exists() and line.lead_id and line.lead_id.id:  # Ensure line and lead exist
                    feedback_lines.append((0, 0, {
                        'review_line_id': line.id,
                        'lead_id': line.lead_id.id,
                        'phone_primary': line.phone_primary or '',
                        'feedback': 'valid',  # Default to valid
                    }))
            
            if feedback_lines:
                res['feedback_line_ids'] = feedback_lines
        
        return res

    def action_create_feedback(self):
        """Create feedback records"""
        self.ensure_one()
        
        if not self.feedback_line_ids:
            raise UserError(_('No feedback lines to create.'))
        
        created_feedbacks = self.env['lost.opportunity.feedback']
        for line in self.feedback_line_ids:
            # Create Lost Opportunity Feedback
            feedback = self.env['lost.opportunity.feedback'].create({
                'review_id': self.review_id.id,
                'lead_id': line.lead_id.id,
                'phone_primary': line.phone_primary,
                'feedback': line.feedback,
                'description': line.description if line.feedback == 'not_valid' else '',
                'date': fields.Date.today(),
                'state': 'confirmed',  # Auto-confirm feedback
            })
            created_feedbacks |= feedback
            
            # Update the review line with feedback
            if line.review_line_id:
                line.review_line_id.write({
                    'feedback': line.feedback,
                    'notes': line.description if line.feedback == 'not_valid' else ''
                })
        
        # Check if we've reached the 10% target and auto-mark as done
        if self.review_id:
            # Count total feedbacks for this review
            total_feedbacks = self.env['lost.opportunity.feedback'].search_count([
                ('review_id', '=', self.review_id.id)
            ])
            
            # If we've reached or exceeded the 10% target, mark as done
            if total_feedbacks >= self.review_id.ten_percent_count and self.review_id.state != 'done':
                self.review_id.write({'state': 'done'})
        
        # Close the wizard and refresh the review form
        return {'type': 'ir.actions.act_window_close'}


class LostReviewFeedbackWizardLine(models.TransientModel):
    _name = 'lost.review.feedback.wizard.line'
    _description = 'Feedback Wizard Line'

    wizard_id = fields.Many2one('lost.review.feedback.wizard', string='Wizard', required=True, ondelete='cascade')
    review_line_id = fields.Many2one('lost.opportunity.review.line', string='Review Line', readonly=True)
    lead_id = fields.Many2one('crm.lead', string='Opportunity', required=True, readonly=True)
    salesperson_id = fields.Many2one(related='lead_id.user_id', string='Salesperson', readonly=True, store=False)
    phone_primary = fields.Char(string='Phone', readonly=True)
    feedback = fields.Selection([
        ('valid', 'Valid'),
        ('not_valid', 'Not Valid')
    ], string='Valid/Not Valid', required=True, default='valid')
    description = fields.Text(string='Description', help='Required if feedback is Not Valid')

    @api.onchange('feedback')
    def _onchange_feedback(self):
        """Clear description if feedback is valid"""
        if self.feedback == 'valid':
            self.description = False

    @api.constrains('feedback', 'description')
    def _check_description(self):
        """Ensure description is filled if feedback is not valid"""
        for record in self:
            if record.feedback == 'not_valid' and not record.description:
                raise UserError(_('Description is required when feedback is "Not Valid".'))

