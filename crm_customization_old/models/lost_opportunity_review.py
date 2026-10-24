from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
import random


class LostOpportunityReview(models.Model):
    _name = 'lost.opportunity.review'
    _description = 'Lost Opportunity Review'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'review_date desc'

    name = fields.Char(string='Review Reference', required=True, copy=False, readonly=True, 
                       default='New', tracking=True)
    date_from = fields.Date(string='Date From', required=True, default=fields.Date.today, 
                           tracking=True)
    date_to = fields.Date(string='Date To', required=True, default=fields.Date.today, 
                         tracking=True)
    review_date = fields.Date(string='Review Date', required=True, default=fields.Date.today, 
                              tracking=True)
    line_ids = fields.One2many('lost.opportunity.review.line', 'review_id', 
                               string='Review Lines')
    total_lost_count = fields.Integer(string='Total Lost in Period', 
                                       compute='_compute_lost_counts', store=True)
    reviewed_count = fields.Integer(string='Reviewed Count', 
                                    compute='_compute_lost_counts', store=True)
    selected_count = fields.Integer(string='Selected Count', 
                                     compute='_compute_selected_count', store=False)
    ten_percent_count = fields.Integer(string='10% Count', 
                                       compute='_compute_lost_counts', store=True)
    review_percentage = fields.Float(string='Review Percentage (%)', 
                                     compute='_compute_lost_counts', store=True)
    selection_status = fields.Selection([
        ('under', 'Under Target'),
        ('at', 'At Target'),
        ('over', 'Over Target')
    ], string='Selection Status', compute='_compute_selected_count', store=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done')
    ], string='Status', default='draft', required=True, tracking=True)
    feedback_count = fields.Integer(string='Feedback Count', compute='_compute_feedback_count')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('lost.opportunity.review') or 'New'

        return super(LostOpportunityReview, self).create(vals)

    @api.onchange('date_from', 'date_to')
    def _onchange_dates(self):
        """Auto-load lost opportunities when dates change"""
        # Auto-load for both new and existing records
        if self.date_from and self.date_to and self.state != 'done':
            if self.id:
                # For existing records, auto-load
                self._load_opportunities()

    @api.constrains('date_from', 'date_to')
    def _check_dates_overlap(self):
        """Constraint to prevent overlapping date ranges - runs on save (create/write)"""
        for record in self:
            if record.date_from and record.date_to:
                # Validate date_from <= date_to
                if record.date_from > record.date_to:
                    raise ValidationError(_('Date From cannot be later than Date To.'))

                # Check for overlapping periods, excluding current record
                record._check_date_overlap(record.date_from, record.date_to, exclude_id=record.id)

    def write(self, vals):
        """Override write to auto-load when dates change"""
        res = super(LostOpportunityReview, self).write(vals)

        # If dates changed and state is not done, auto-load opportunities
        if ('date_from' in vals or 'date_to' in vals):
            for record in self:
                if record.state != 'done' and record.date_from and record.date_to:
                    record._load_opportunities()

        return res
    
    def _check_date_overlap(self, date_from, date_to, exclude_id=None):
        """Check if the date range overlaps with any existing review"""
        # Convert to date objects if strings
        if isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        # Build domain to find overlapping reviews
        # Two periods overlap if: period1_start <= period2_end AND period1_end >= period2_start
        domain = [
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from),
        ]

        # Exclude current record if editing
        if exclude_id:
            domain.append(('id', '!=', exclude_id))

        overlapping_reviews = self.env['lost.opportunity.review'].search(domain, limit=1)

        if overlapping_reviews:
            raise ValidationError(_(
                'Cannot create or modify review with overlapping date period.\n\n'
                'An existing review "%s" already covers dates from %s to %s.\n\n'
                'Please choose a different date range that does not overlap with existing reviews.'
            ) % (
                overlapping_reviews.name,
                overlapping_reviews.date_from.strftime('%Y-%m-%d'),
                overlapping_reviews.date_to.strftime('%Y-%m-%d')
            ))

    @api.depends('line_ids', 'date_from', 'date_to')
    def _compute_lost_counts(self):
        """Compute total lost opportunities and reviewed count for the date range"""
        for record in self:
            if not record.date_from or not record.date_to:
                record.total_lost_count = 0
                record.ten_percent_count = 0
                record.reviewed_count = 0
                record.review_percentage = 0
                continue
            
            # Get lost stages
            lost_stages = self.env['crm.stage'].search([('is_lost', '=', True)])
            
            # Build base domain
            domain = [
                ('ibs_closed_at', '!=', False),
                ('ibs_closed_at', '>=', f"{record.date_from} 00:00:00"),
                ('ibs_closed_at', '<=', f"{record.date_to} 23:59:59"),
            ]
            
            # Add stage condition
            if lost_stages:
                domain.append(('stage_id', 'in', lost_stages.ids))
            else:
                # Fallback: search by lost_reason_id (if opportunity has lost reason, it's lost)
                domain.append(('lost_reason_id', '!=', False))
            
            total_lost = self.env['crm.lead'].search_count(domain)
            
            record.total_lost_count = total_lost
            record.ten_percent_count = max(1, int(total_lost * 0.1)) if total_lost > 0 else 0
            record.reviewed_count = len(record.line_ids)
            record.review_percentage = (record.reviewed_count / record.total_lost_count * 100) if record.total_lost_count > 0 else 0

    @api.depends('line_ids.selected', 'ten_percent_count')
    def _compute_selected_count(self):
        """Compute selected count and status"""
        for record in self:
            selected_count = len(record.line_ids.filtered(lambda l: l.selected))
            record.selected_count = selected_count
            
            # Determine status based on target
            if record.ten_percent_count > 0:
                if selected_count > record.ten_percent_count:
                    record.selection_status = 'over'
                elif selected_count == record.ten_percent_count:
                    record.selection_status = 'at'
                else:
                    record.selection_status = 'under'
            else:
                record.selection_status = 'under'
    
    def _compute_feedback_count(self):
        """Compute the number of feedbacks linked to this review"""
        for record in self:
            record.feedback_count = self.env['lost.opportunity.feedback'].search_count([
                ('review_id', '=', record.id)
            ])

    def action_pick_randomly(self):
        """Pick 10% of period's lost opportunities randomly and open feedback wizard"""
        self.ensure_one()
        
        # Get lost stages (is_lost = True)
        lost_stages = self.env['crm.stage'].search([('is_lost', '=', True)])
        
        # Build domain for date range lost opportunities
        domain = [
            ('ibs_closed_at', '!=', False),
            ('ibs_closed_at', '>=', f"{self.date_from} 00:00:00"),
            ('ibs_closed_at', '<=', f"{self.date_to} 23:59:59"),
        ]
        
        if lost_stages:
            domain.append(('stage_id', 'in', lost_stages.ids))
        else:
            # Fallback: search by lost_reason_id
            domain.append(('lost_reason_id', '!=', False))
        
        # Get all lost opportunities for the period
        lost_opportunities = self.env['crm.lead'].search(domain)
        
        if not lost_opportunities:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Lost Opportunities',
                    'message': 'No lost opportunities found for this date range.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Calculate 10% of total count
        total_count = len(lost_opportunities)
        pick_count = max(1, int(total_count * 0.1))  # At least 1 if there are any
        
        # Get already reviewed lead IDs (leads that already have feedback)
        existing_feedback_lead_ids = self.env['lost.opportunity.feedback'].search([
            ('review_id', '=', self.id)
        ]).mapped('lead_id').ids
        
        # Filter out already reviewed opportunities
        available_opportunities = lost_opportunities.filtered(lambda l: l.id not in existing_feedback_lead_ids)
        
        if not available_opportunities:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'All Reviewed',
                    'message': 'All lost opportunities for this period have already been reviewed.',
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Randomly select opportunities
        selected_count = min(pick_count, len(available_opportunities))
        selected_opportunities = random.sample(list(available_opportunities), selected_count)
        
        # Create or update review lines and mark them as selected
        created_lines = self.env['lost.opportunity.review.line']
        for opportunity in selected_opportunities:
            # Check if line already exists
            existing_line = self.line_ids.filtered(lambda l: l.lead_id.id == opportunity.id)
            if existing_line:
                existing_line.write({'selected': True})
                created_lines |= existing_line
            else:
                line = self.env['lost.opportunity.review.line'].create({
                    'review_id': self.id,
                    'lead_id': opportunity.id,
                    'contact_name': opportunity.partner_id.name or opportunity.contact_name or 'N/A',
                    'salesperson_id': opportunity.user_id.id if opportunity.user_id else False,
                    'phone_primary': opportunity.phone or opportunity.mobile or 'N/A',
                    'selected': True,  # Mark as selected
                })
                created_lines |= line
        
        # Update state to in_progress if it was draft
        if self.state == 'draft':
            self.state = 'in_progress'
        
        # Open the feedback wizard directly with the selected lines
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Feedback (10% Random)',
            'res_model': 'lost.review.feedback.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_review_id': self.id,
                'selected_line_ids': created_lines.ids,
            }
        }

    def _load_opportunities(self):
        """Internal method to load lost opportunities"""
        self.ensure_one()
        
        if not self.date_from or not self.date_to:
            return
        
        # Get lost stages
        lost_stages = self.env['crm.stage'].search([('is_lost', '=', True)])
        
        # Build domain for date range lost opportunities
        domain = [
            ('ibs_closed_at', '!=', False),
            ('ibs_closed_at', '>=', f"{self.date_from} 00:00:00"),
            ('ibs_closed_at', '<=', f"{self.date_to} 23:59:59"),
        ]
        
        if lost_stages:
            domain.append(('stage_id', 'in', lost_stages.ids))
        else:
            # Fallback: search by lost_reason_id
            domain.append(('lost_reason_id', '!=', False))
        
        # Get all lost opportunities in period
        lost_opportunities = self.env['crm.lead'].search(domain)
        
        # Clear existing lines
        self.line_ids.unlink()
        
        if lost_opportunities:
            # Create lines for all lost opportunities (readonly, with tick checkbox)
            for opportunity in lost_opportunities:
                self.env['lost.opportunity.review.line'].create({
                    'review_id': self.id,
                    'lead_id': opportunity.id,
                    'contact_name': opportunity.partner_id.name or opportunity.contact_name or 'N/A',
                    'salesperson_id': opportunity.user_id.id if opportunity.user_id else False,
                    'phone_primary': opportunity.phone or opportunity.mobile or 'N/A',
                    'selected': False,  # Not selected by default
                })
            
            # Update state to in_progress
            if self.state == 'draft':
                self.state = 'in_progress'

    def action_load_lost_opportunities(self):
        """Load all lost opportunities in the date range (button action)"""
        self.ensure_one()
        
        self._load_opportunities()
        
        message = f'{len(self.line_ids)} lost opportunities have been loaded. Please tick the ones to review.' if self.line_ids else 'No lost opportunities found for this date range.'
        message_type = 'success' if self.line_ids else 'warning'
        
        # Return True to refresh the view automatically
        return True

    def action_add_line(self):
        """Open a wizard to manually add lost opportunities to review"""
        self.ensure_one()
        
        # Get lost stages
        lost_stages = self.env['crm.stage'].search([('is_lost', '=', True)])
        
        # Build domain for date range lost opportunities
        domain = [
            ('ibs_closed_at', '!=', False),
            ('ibs_closed_at', '>=', f"{self.date_from} 00:00:00"),
            ('ibs_closed_at', '<=', f"{self.date_to} 23:59:59"),
        ]
        
        if lost_stages:
            domain.append(('stage_id', 'in', lost_stages.ids))
        else:
            # Fallback: search by lost_reason_id
            domain.append(('lost_reason_id', '!=', False))
        
        # Get already reviewed lead IDs
        existing_lead_ids = self.line_ids.mapped('lead_id').ids
        if existing_lead_ids:
            domain.append(('id', 'not in', existing_lead_ids))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Lost Opportunities',
            'res_model': 'crm.lead',
            'view_mode': 'list',
            'domain': domain,
            'target': 'new',
            'context': {'review_id': self.id}
        }

    def action_mark_done(self):
        """Mark review as done"""
        self.write({'state': 'done'})

    def action_reset_to_draft(self):
        """Reset review to draft"""
        self.write({'state': 'draft'})

    def action_create_feedback(self):
        """Create feedback records for selected lines"""
        self.ensure_one()
        
        # Get selected lines
        selected_lines = self.line_ids.filtered(lambda l: l.selected)
        
        if not selected_lines:
            raise UserError(_('Please select at least one opportunity to create feedback.'))
        
        # Open wizard to create feedback
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Feedback',
            'res_model': 'lost.review.feedback.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_review_id': self.id,
                'selected_line_ids': selected_lines.ids,  # Pass as custom context key
            }
        }
    
    def action_view_feedbacks(self):
        """View feedbacks linked to this review"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Feedbacks',
            'res_model': 'lost.opportunity.feedback',
            'view_mode': 'list,form',
            'domain': [('review_id', '=', self.id)],
            'context': {'default_review_id': self.id}
        }


class LostOpportunityReviewLine(models.Model):
    _name = 'lost.opportunity.review.line'
    _description = 'Lost Opportunity Review Line'
    _order = 'create_date desc'

    review_id = fields.Many2one('lost.opportunity.review', string='Review', 
                                required=True, ondelete='cascade')
    lead_id = fields.Many2one('crm.lead', string='Opportunity', required=True, readonly=True)
    selected = fields.Boolean(string='Select', default=False, help='Tick to include in feedback creation')
    contact_name = fields.Char(string='Contact Name', required=True, readonly=True)
    salesperson_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    phone_primary = fields.Char(string='Phone Primary', readonly=True)
    feedback = fields.Selection([
        ('valid', 'Valid'),
        ('not_valid', 'Not Valid')
    ], string='Feedback', help='Validation status of the lost opportunity')
    notes = fields.Text(string='Notes')
    
    # Related fields for convenience
    lead_name = fields.Char(related='lead_id.name', string='Opportunity Name', readonly=True)
    lead_stage = fields.Char(related='lead_id.stage_id.name', string='Stage', readonly=True)
    lost_reason_id = fields.Many2one('crm.lost.reason', related='lead_id.lost_reason_id', string='Lost Reason', readonly=True)

    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        """Auto-fill fields when lead is selected"""
        if self.lead_id:
            self.contact_name = self.lead_id.partner_id.name or self.lead_id.contact_name or 'N/A'
            self.salesperson_id = self.lead_id.user_id.id if self.lead_id.user_id else False
            self.phone_primary = self.lead_id.phone or self.lead_id.mobile or 'N/A'

