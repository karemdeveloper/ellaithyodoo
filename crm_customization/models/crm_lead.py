from odoo import models, fields, api,_
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import pytz
import math

from odoo.exceptions import AccessError


class CrmLead(models.Model):
    _inherit = 'crm.lead'
    
    branch_name = fields.Many2one('res.branch', string="Branch")
    area_name = fields.Many2one('res.area', string="Area")
    # brand_name = fields.Many2one('res.brand', string="Brand", required=True)
    brand_name2 = fields.Many2many('res.brand', string="Brand(s)")

    source_name = fields.Many2one('res.source', string="Source")
    sales_team = fields.Many2one('crm.team', string="Sales team")
    # sub_brand_name = fields.Many2one('res.sub.brand', string="Sub Brand", required=True)
    sub_brand_name2 = fields.Many2many('res.sub.brand', string="Sub Brand(s)")

    sla_duration = fields.Char(string="SLA Duration", compute='_compute_sla_duration')
    marketing_offer=fields.Many2one('marketing.offers',string='Marketing offer')
    call_type=fields.Many2one('call.type',string='Call Type')
    feedback_ids = fields.One2many('crm.feedback', 'lead_id', string="Feedback Lines")
    has_feedback = fields.Boolean(string="Has Feedback", default=False)
    sub_brand_used_id = fields.Many2many(
        'res.sub.brand',
        'opportunity_used_sub_brand_rel',
        'wizard_id',
        'sub_brand_id',
        string="Used Sub Brand(s)"
    )
    brand_used_id = fields.Many2many(
        'res.brand',
        'opportunity_used_brand_rel',
        'wizard_id',
        'brand_id',
        string="Used Brand(s)")
    model = fields.Char(string="Model")
    kilometers = fields.Char(string="Kilometers")
    opportunity_type = fields.Selection([
        ('new', 'New'),
        ('trade_in', 'Trade In'),
        ('used', 'Used'),
        ('service', 'Service'),
    ], string='Opportunity Type', tracking=True)
    
    # Service field - only shown when opportunity_type is 'service'
    service_id = fields.Many2one('res.service', string='Service', tracking=True)
    
    # Won wizard fields
    chassis_number = fields.Char(string='Chassis/Serial Number', tracking=True)
    sale_order_id = fields.Char(string='Sales Order', tracking=True)
    
    opportunity_type_display = fields.Char(
        string='Type',
        compute='_compute_opportunity_type_display',
        store=False
    )
    ibs_closed_at = fields.Datetime(string='IBS Closed At', tracking=True,
                                     help='Date and time when the opportunity was marked as lost')

    is_new_within_2hrs = fields.Boolean(
        string='New Within 2 Hours',
        compute='_compute_is_new_within_2hrs',
        search='_search_is_new_within_2hrs',
        help='Opportunity created within last 2 hours and still in new stage'
    )

    is_new_more_than_2hrs = fields.Boolean(
        string='New More Than 2 Hours',
        compute='_compute_is_new_more_than_2hrs',
        search='_search_is_new_more_than_2hrs',
        help='Opportunity created more than 2 hours ago and still in new stage'
    )
    hotline_transfer = fields.Boolean(string='Hotline-Transfer',default=False)
    # Override _search to apply domain for group_view_unassigned_opportunities
    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """Override search to hide opportunities without salesperson from users without special access"""
        # Check if user does NOT have the special group to view unassigned opportunities
        if not self.env.user.has_group('crm_customization.group_view_unassigned_opportunities'):
            # Add domain to filter out opportunities without user_id (salesperson)
            domain = domain + [('user_id', '!=', False)]
        
        return super()._search(domain, offset=offset, limit=limit, order=order)
######################################################################################
    # override create to enforce access rights and restrict opportunity creation based on open opportunities
    @api.model
    def create(self, vals):
        # Check basic CRM create access
        if not self.env.user.has_group("crm_customization.group_crm_user_create"):
            raise AccessError(_("You are not allowed to create CRM Leads."))

        # ---------------------------------------------------------
        # Access Control: Restrict opportunity creation
        # ---------------------------------------------------------
        if not vals.get('name'):
            branch_id = vals.get('branch_name')
            print("Branch ID from vals:", branch_id)  # Debug print

            # ✅ fallback from user if not exist
            if not branch_id:
                user = self.env.user
                if user.sale_team_id and user.sale_team_id.branch_name:
                    branch_id = user.sale_team_id.branch_name.id
                    print("Branch ID from user sale team:", branch_id)  # Debug print

            if branch_id:
                vals['name'] = self._generate_lead_name(branch_id)
                print("Generated lead name:", vals['name'])  # Debug print
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('crm.lead') or 'New'
                print("Generated lead name from default sequence:", vals['name'])  # Debug print

        if vals.get('type') == 'opportunity' and vals.get('partner_id'):
            # check if user has the special group to bypass the open opportunity restriction
            has_full_access = self.env.user.has_group(
                'crm_customization.group_access_create_opportunity'
            )
            # if user does not have the special group, enforce the restriction of one open opportunity per customer
            if not has_full_access:
                partner_id = vals.get('partner_id')

                # Count open opportunities (not won and not lost)
                open_opps_count = self.search_count([
                    ('partner_id', '=', partner_id),
                    ('type', '=', 'opportunity'),
                    # probability < 100 means not won, active=True means not lost (since lost stage sets active=False)
                    ('probability', '<', 100),
                    ('active', '=', True)
                ])
                # if there are any open opportunities for this customer, prevent creation of a new one
                if open_opps_count > 0:
                    raise ValidationError(
                        _("Cannot add opportunity. Customer already has an open opportunity.")
                    )

        return super().create(vals)
#######################################################################################
    @api.depends('opportunity_type')
    def _compute_opportunity_type_display(self):
        """Display opportunity type as short code"""
        type_map = {
            'new': 'N',
            'used': 'U',
            'trade_in': 'T',
            'service': 'S',
        }
        for rec in self:
            rec.opportunity_type_display = type_map.get(rec.opportunity_type, '')

    def _compute_is_new_within_2hrs(self):
        """Check if opportunity was created within last 2 hours and is still in new stage"""
        from datetime import timedelta

        # Get the "New" stage - search by sequence, ordered
        new_stage = self.env['crm.stage'].search([], order='sequence asc', limit=1)

        for rec in self:
            if rec.create_date and new_stage:
                two_hours_ago = fields.Datetime.now() - timedelta(hours=2)
                rec.is_new_within_2hrs = (
                    rec.create_date >= two_hours_ago and
                    rec.stage_id.id == new_stage.id
                )
            else:
                rec.is_new_within_2hrs = False

    def _search_is_new_within_2hrs(self, operator, value):
        """Search method for is_new_within_2hrs field"""
        from datetime import timedelta

        two_hours_ago = fields.Datetime.now() - timedelta(hours=2)
        # Get the first stage (New stage)
        new_stage = self.env['crm.stage'].search([], order='sequence asc', limit=1)

        if (operator == '=' and value) or (operator == '!=' and not value):
            # Search for opportunities within 2 hours in new stage
            domain = [
                ('create_date', '>=', two_hours_ago),
            ]
            if new_stage:
                domain.append(('stage_id', '=', new_stage.id))
            return domain
        else:
            # Search for opportunities NOT within 2 hours or not in new stage
            if new_stage:
                return ['|',
                    ('create_date', '<', two_hours_ago),
                    ('stage_id', '!=', new_stage.id)
                ]
            else:
                return [('create_date', '<', two_hours_ago)]

    @api.depends('create_date', 'stage_id')
    def _compute_is_new_more_than_2hrs(self):
        """Check if opportunity was created more than 2 hours ago and is still in new stage"""
        from datetime import timedelta

        # Get the "New" stage - search by sequence, ordered
        new_stage = self.env['crm.stage'].search([], order='sequence asc', limit=1)

        for rec in self:
            if rec.create_date and new_stage:
                two_hours_ago = fields.Datetime.now() - timedelta(hours=2)
                rec.is_new_more_than_2hrs = (
                    rec.create_date < two_hours_ago and
                    rec.stage_id.id == new_stage.id
                )
            else:
                rec.is_new_more_than_2hrs = False

    def _search_is_new_more_than_2hrs(self, operator, value):
        """Search method for is_new_more_than_2hrs field"""
        from datetime import timedelta

        two_hours_ago = fields.Datetime.now() - timedelta(hours=2)
        # Get the first stage (New stage)
        new_stage = self.env['crm.stage'].search([], order='sequence asc', limit=1)

        if (operator == '=' and value) or (operator == '!=' and not value):
            # Search for opportunities more than 2 hours old in new stage
            domain = [
                ('create_date', '<', two_hours_ago),
            ]
            if new_stage:
                domain.append(('stage_id', '=', new_stage.id))
            return domain
        else:
            # Search for opportunities within 2 hours or not in new stage
            if new_stage:
                return ['|',
                    ('create_date', '>=', two_hours_ago),
                    ('stage_id', '!=', new_stage.id)
                ]
            else:
                return [('create_date', '>=', two_hours_ago)]

    def debug_new_within_2hrs(self):
        """Debug method to test the filter logic"""
        from datetime import timedelta
        import logging
        _logger = logging.getLogger(__name__)

        two_hours_ago = fields.Datetime.now() - timedelta(hours=2)
        new_stage = self.env['crm.stage'].search([], order='sequence asc', limit=1)

        _logger.info(f"Two hours ago: {two_hours_ago}")
        _logger.info(f"New stage: {new_stage.name if new_stage else 'Not found'} (ID: {new_stage.id if new_stage else 'N/A'})")

        for rec in self:
            _logger.info(f"Lead: {rec.name}, Created: {rec.create_date}, Stage: {rec.stage_id.name} (ID: {rec.stage_id.id})")
            _logger.info(f"  Within 2hrs? {rec.create_date >= two_hours_ago if rec.create_date else False}")
            _logger.info(f"  In new stage? {rec.stage_id.id == new_stage.id if new_stage else False}")

    ###################################################################################
    @api.constrains('phone', 'mobile')
    def _check_phone_length(self):
        """Validate that phone numbers have at least 11 digits"""
        for record in self:
            if record.phone:
                phone_digits = ''.join(filter(str.isdigit, record.phone))
                if len(phone_digits) < 11:
                    raise ValidationError(
                        f'Phone number must contain at least 11 digits. Current: {len(phone_digits)} digits'
                    )
            if record.mobile:
                mobile_digits = ''.join(filter(str.isdigit, record.mobile))
                if len(mobile_digits) < 11:
                    raise ValidationError(
                        f'Mobile number must contain at least 11 digits. Current: {len(mobile_digits)} digits'
                    )

    @api.model
    def default_get(self, fields_list):
        """Set default branch from current user's sales team"""
        defaults = super().default_get(fields_list)
        if 'branch_name' in fields_list and 'branch_name' not in defaults:
            user = self.env.user
            if user.sale_team_id and user.sale_team_id.branch_name:
                defaults['branch_name'] = user.sale_team_id.branch_name.id
        return defaults

    @api.onchange('brand_name2')
    def _onchange_brand_name2(self):
        """Clear sub-brands when brands change (New section)"""
        for rec in self:
            if rec.brand_name2:
                # Keep only sub-brands that belong to selected brands
                valid_sub_brands = rec.sub_brand_name2.filtered(lambda sb: sb.brand in rec.brand_name2)
                rec.sub_brand_name2 = valid_sub_brands
            else:
                # If no brands selected, clear all sub-brands
                rec.sub_brand_name2 = False

    @api.onchange('brand_used_id')
    def _onchange_brand_used_id(self):
        """Clear sub-brands when brands change (Used section)"""
        for rec in self:
            if rec.brand_used_id:
                # Keep only sub-brands that belong to selected brands
                valid_sub_brands = rec.sub_brand_used_id.filtered(lambda sb: sb.brand in rec.brand_used_id)
                rec.sub_brand_used_id = valid_sub_brands
            else:
                # If no brands selected, clear all sub-brands
                rec.sub_brand_used_id = False
########################################################################################
    def _format_timedelta(self, seconds):
        # Format seconds -> HH:MM:SS
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @api.depends('create_date', 'feedback_ids.date')
    def _compute_sla_duration(self):
        for rec in self:
            if not rec.create_date:
                rec.sla_duration = "00:00:00"
                continue

            # find first feedback date if any
            feedback_date = False
            if rec.feedback_ids:
                # take the earliest feedback record date
                fb = rec.feedback_ids.sorted('date')[0]
                feedback_date = fb.date

            # compute end time: feedback_date if exists else now (server time)
            if feedback_date:
                try:
                    start_dt = fields.Datetime.from_string(rec.create_date)
                    end_dt = fields.Datetime.from_string(feedback_date)
                    delta = (end_dt - start_dt).total_seconds()
                except Exception:
                    delta = 0
            else:
                # if no feedback yet, compute relative to now (server)
                try:
                    start_dt = fields.Datetime.from_string(rec.create_date)
                    now_dt = fields.Datetime.now()
                    delta = (now_dt - start_dt).total_seconds()
                except Exception:
                    delta = 0

            if delta < 0:
                delta = 0
            rec.sla_duration = self._format_timedelta(delta)
##########################################################################################
    def action_open_feedback_wizard(self):
        """Open the feedback wizard for selected leads"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.feedback.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_ids': [(6, 0, self.ids)],
            }
        }

    def action_open_won_wizard(self):
        """Open the won wizard to mark opportunity as won"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Mark as Won',
            'res_model': 'opportunity.won.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
            }
        }

################################################################################################
    late_days = fields.Integer(string="Late Days", compute='_compute_late_days', store=True)

    @api.depends('sla_duration')
    def _compute_late_days(self):
        """Compute late_days as floor(total_hours / 9).
        sla_duration is expected to be 'HH:MM:SS' (string).
        """
        for rec in self:
            rec.late_days = 0
            sd = rec.sla_duration or ''
            # handle cases: empty, already in HH:MM:SS, or unexpected format
            try:
                parts = sd.split(':')
                if len(parts) == 3:
                    hh = float(parts[0])
                    mm = float(parts[1])
                    ss = float(parts[2])
                    total_hours = hh + (mm / 60.0) + (ss / 3600.0)
                elif len(parts) == 2:
                    # sometimes could be "HH:MM"
                    hh = float(parts[0])
                    mm = float(parts[1])
                    total_hours = hh + (mm / 60.0)
                elif sd.strip() != '':
                    # try to parse as float number of hours (e.g., "2.7")
                    total_hours = float(sd)
                else:
                    total_hours = 0.0

                # divide by 9 and take integer part (floor)
                rec.late_days = int(math.floor(total_hours / 9.0))
            except Exception:
                # on any parse error, fallback to 0
                rec.late_days = 0

    def write(self, vals):
        """Override write method to remove 'active' condition from date_closed logic"""
        # Validate stage change BEFORE any processing
        if 'stage_id' in vals and vals.get('stage_id'):
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            
            # Check if any lead is changing stage
            for lead in self:
                if lead.stage_id.id != vals['stage_id']:
                    # Check if it's Lost stage from drag and drop (not from Lost wizard/button)
                    # Lost wizard sets ibs_closed_at or active=False, drag and drop doesn't
                    if new_stage.is_lost and 'ibs_closed_at' not in vals and vals.get('active', True):
                        raise UserError(
                            _("Cannot move opportunity to Lost stage via drag and drop.\n\n"
                              "Please use the 'Lost' button to properly mark the opportunity as lost.")
                        )
                    if new_stage.is_won and not self.env.context.get('from_won_wizard'):
                        raise UserError(
                            _("Cannot move opportunity to Won via drag and drop / statusbar.\n\n"
                            "Please use the 'Won' button.")
                        )
                    # Check required fields before allowing stage change
                    missing_fields = []
                    if not lead.branch_name:
                        missing_fields.append('Branch')
                    if not lead.brand_name2:
                        missing_fields.append('Brand')
                    if not lead.sub_brand_name2:
                        missing_fields.append('Sub Brand')
                    if not lead.source_name:
                        missing_fields.append('Source')
                    if not lead.call_type:
                        missing_fields.append('Call Type')
                    if not lead.user_id:
                        missing_fields.append('Salesperson')
                    if not lead.phone and not lead.mobile:
                        missing_fields.append('Phone/Mobile')
                    
                    if missing_fields:
                        raise UserError(
                            _("Cannot change stage. Please fill the following required fields first:\n\n• %s") 
                            % '\n• '.join(missing_fields)
                        )
        
        if vals.get('website'):
            vals['website'] = self.env['res.partner']._clean_website(vals['website'])

        now = self.env.cr.now()
        stage_updated, stage_is_won = False, False
        # stage change (or reset): update date_last_stage_update if at least one
        # lead does not have the same stage
        if 'stage_id' in vals:
            stage_updated = any(lead.stage_id.id != vals['stage_id'] for lead in self)
            
            if stage_updated:
                vals['date_last_stage_update'] = now
            if stage_updated and vals.get('stage_id'):
                stage = self.env['crm.stage'].browse(vals['stage_id'])
                if stage.is_won:
                    vals.update({'probability': 100, 'automated_probability': 100})
                    stage_is_won = True
        # user change; update date_open if at least one lead does not
        # have the same user
        if 'user_id' in vals and not vals.get('user_id'):
            vals['date_open'] = False
        elif vals.get('user_id'):
            user_updated = any(lead.user_id.id != vals['user_id'] for lead in self)
            if user_updated:
                vals['date_open'] = now

        # CUSTOMIZED: stage change with new stage: update probability and date_closed
        # Removed 'not vals.get('active', True)' condition - only set date_closed when probability >= 100
        if vals.get('probability', 0) >= 100:
            vals['date_closed'] = fields.Datetime.now()
        elif vals.get('probability', 0) > 0:
            vals['date_closed'] = False
        elif stage_updated and not stage_is_won and not 'probability' in vals:
            vals['date_closed'] = False

        if any(field in ['active', 'stage_id'] for field in vals):
            self._handle_won_lost(vals)

        # Sync user_id changes to related partner
        if 'user_id' in vals:
            for lead in self:
                if lead.partner_id:
                    lead.partner_id.write({'user_id': vals['user_id']})
        if not stage_is_won:
            return super(CrmLead, self).write(vals)

        # stage change between two won stages: does not change the date_closed
        leads_already_won = self.filtered(lambda lead: lead.stage_id.is_won)
        remaining = self - leads_already_won
        if remaining:
            result = super(CrmLead, remaining).write(vals)
        if leads_already_won:
            vals.pop('date_closed', False)
            result = super(CrmLead, leads_already_won).write(vals)
        return result

    def copy(self, default=None):
        if not self.env.user._is_admin():
            raise AccessError(_("You are not allowed to duplicate CRM leads."))
        return super().copy(default=default)
################################################################################

    not_lead_access = fields.Boolean(
        compute="_compute_not_lead_access"
    )

    @api.depends_context('uid')
    def _compute_not_lead_access(self):
        for rec in self:
            is_sales_group = rec.env.user.has_group(
                'sales_team.group_sale_manager'
            )
            is_salesman_all_leads = rec.env.user.has_group(
                'sales_team.group_sale_salesman_all_leads'
            )

            rec.not_lead_access = not (
                is_sales_group or is_salesman_all_leads or not rec.id
            )
##########################################################################################
    def copy(self, default=None):
        """
        if not sales manager cannot duplicate lead records, raise error
        """
        self.ensure_one()

        # check group
        if not self.env.user.has_group('sales_team.group_sale_manager'):
            raise UserError(_("You are not allowed to duplicate Opportunity records. Please contact Sales Manager."))
        return super(CrmLead, self).copy(default)
