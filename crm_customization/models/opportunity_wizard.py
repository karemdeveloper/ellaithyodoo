from odoo import models, fields, api
from datetime import datetime
from datetime import timedelta

import logging
import time
import pytz

_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError

class OpportunityWizard(models.TransientModel):
    _name = 'opportunity.wizard'
    _description = 'Opportunity Wizard'

    name = fields.Char(string="Opportunity Name", required=True)
    brand_id = fields.Many2one('res.brand', string="Brand", required=False)
    brand_id2 = fields.Many2many('res.brand', string="Brand(s)", required=False)
    brand_used_id = fields.Many2many(
        'res.brand',
        'opportunity_wizard_used_brand_rel',
        'wizard_id',
        'brand_id',
        string="Used Brand(s)"
    )
    opportunity_type = fields.Selection([
        ('new', 'New'),
        ('trade_in', 'Trade In'),
        ('used', 'Used'),
        ('service', 'Service'),
    ], string='Opportunity Type', default='new')
    sub_brand_id = fields.Many2one('res.sub.brand', string="Sub Brand", required=False)
    sub_brand_id2 = fields.Many2many('res.sub.brand', string="Sub Brand(s)", required=False)
    sub_brand_used_id = fields.Many2many(
        'res.sub.brand',
        'opportunity_wizard_used_sub_brand_rel',
        'wizard_id',
        'sub_brand_id',
        string="Used Sub Brand(s)"
    )
    area_id = fields.Many2one('res.area', string="Area",required=True)
    branch_id = fields.Many2one('res.branch', string="Branch",required=True)
    source_id = fields.Many2one('res.source', string="Source", required=True)
    sla_duration = fields.Float(string="SLA Duration")
    partner_id = fields.Many2one('res.partner', string="Customer")
    marketing_offer = fields.Many2one('marketing.offers', string='Marketing Offer')
    call_type = fields.Many2one('call.type', string='Call Type', required=True)
    model = fields.Char(string="Model")
    kilometers = fields.Char(string="Kilometers")
    service_id = fields.Many2one('res.service', string='Service')
    hotline_transfer = fields.Boolean(string='Hotline-Transfer',default=False)


    @api.model
    def default_get(self, fields_list):
        """Pre-fill the popup without leaking res.source into utm.source."""
        res = super().default_get(fields_list)

        popup_source_id = self.env.context.get('ellaithy_popup_source_id')
        if popup_source_id:
            res['source_id'] = popup_source_id

        if not self.env.context.get('default_partner_id'):
            partner_id = self.env.context.get('active_id')
            if partner_id:
                partner = self.env['res.partner'].browse(partner_id).exists()
                if partner:
                    res.update({
                        'partner_id': partner.id,
                        'name': partner.name or '',
                        'area_id': partner.area_id.id or False,
                        'branch_id': partner.branch_id.id or False,
                        'source_id': partner.crm_source_id.id or False,
                    })
        return res

    @api.onchange('brand_id2')
    def _onchange_brand_id2(self):
        """Clear sub-brands when brands change (New section)"""
        if self.brand_id2:
            # Keep only sub-brands that belong to selected brands
            valid_sub_brands = self.sub_brand_id2.filtered(lambda sb: sb.brand in self.brand_id2)
            self.sub_brand_id2 = valid_sub_brands
        else:
            # If no brands selected, clear all sub-brands
            self.sub_brand_id2 = False

    @api.onchange('brand_used_id')
    def _onchange_brand_used_id(self):
        """Clear sub-brands when brands change (Used section)"""
        if self.brand_used_id:
            # Keep only sub-brands that belong to selected brands
            valid_sub_brands = self.sub_brand_used_id.filtered(lambda sb: sb.brand in self.brand_used_id)
            self.sub_brand_used_id = valid_sub_brands
        else:
            # If no brands selected, clear all sub-brands
            self.sub_brand_used_id = False

    #################################################################################

    def _get_next_salesperson(self):
        """Choose a salesperson without updating any shared pointer.

        This is intentionally stateless for the interactive Create Opportunity
        request.  It respects branch, active CRM team membership and current
        shift, but performs reads only.  A deterministic partner-based index
        spreads new customers across the available sequences without any
        shared-row UPDATE/INSERT that could block another user.
        """
        self.ensure_one()
        if not self.branch_id:
            return False

        sales_teams = self.env['crm.team'].search([
            ('branch_name', '=', self.branch_id.id),
        ])
        if not sales_teams:
            return False

        active_members = self.env['crm.team.member'].search([
            ('crm_team_id', 'in', sales_teams.ids),
            ('state', '=', 'active'),
        ])
        active_user_ids = active_members.mapped('user_id').filtered(
            lambda user: user.active
        ).ids
        if not active_user_ids:
            return False

        sequences = self.env['distribute.sequence'].search([
            ('branch', '=', self.branch_id.id),
            ('state', '=', 'active'),
            ('sales_person', 'in', active_user_ids),
        ], order='sequence asc, id asc')
        if not sequences:
            return False

        utc_now = fields.Datetime.now()
        cairo_tz = pytz.timezone('Africa/Cairo')
        local_now = utc_now.replace(tzinfo=pytz.utc).astimezone(cairo_tz)
        current_hour = local_now.hour + local_now.minute / 60.0

        def in_shift(seq):
            shift = seq.shift
            if not shift:
                return False
            if shift.from_date <= shift.to_date:
                return shift.from_date <= current_hour <= shift.to_date
            return current_hour >= shift.from_date or current_hour <= shift.to_date

        current_sequences = sequences.filtered(in_shift)
        candidates = current_sequences or sequences

        # Stateless and deterministic: no pointer row and therefore no lock.
        key = self.partner_id.id or self.id or 0
        selected = candidates[key % len(candidates)]
        return selected.sales_person if selected.sales_person.active else False

    def action_distribute(self):
        """Minimal, lock-resistant Create Opportunity request.

        Critical path only:
          1. validate customer
          2. choose salesperson using read-only/stateless logic
          3. create crm.lead
          4. return the new form

        No customer write, no round-robin pointer write, and no lead-name
        sequence call are performed by this button.
        """
        self.ensure_one()
        started = time.monotonic()

        if not self.partner_id:
            raise ValidationError(_("Customer is required."))

        # Reuse the customer's active salesperson when available.
        if self.partner_id.user_id and self.partner_id.user_id.active:
            salesperson = self.partner_id.user_id
        else:
            assign_started = time.monotonic()
            salesperson = self._get_next_salesperson()
            _logger.info(
                "Create Opportunity timing: salesperson selection %.3fs",
                time.monotonic() - assign_started,
            )

        # IMPORTANT: pass the wizard name explicitly.  Without this value,
        # crm.lead.create() calls _generate_lead_name(branch_id), which belongs
        # to a separate sequence customization and may contend on shared state.
        opportunity_name = (
            (self.name or '').strip()
            or (self.partner_id.name or '').strip()
            or _("Opportunity")
        )

        create_vals = {
            'name': opportunity_name,
            'sla_duration': '00:00:00',
            'marketing_offer': self.marketing_offer.id,
            'call_type': self.call_type.id,
            'partner_id': self.partner_id.id,
            'branch_name': self.branch_id.id if self.branch_id else False,
            'area_name': self.area_id.id if self.area_id else False,
            'source_name': self.source_id.id,
            'user_id': salesperson.id if salesperson else False,
            'type': 'opportunity',
            'brand_name2': [(6, 0, self.brand_id2.ids)],
            'sub_brand_name2': [(6, 0, self.sub_brand_id2.ids)],
            'brand_used_id': [(6, 0, self.brand_used_id.ids)],
            'sub_brand_used_id': [(6, 0, self.sub_brand_used_id.ids)],
            'model': self.model,
            'opportunity_type': self.opportunity_type,
            'kilometers': self.kilometers,
            'service_id': self.service_id.id if self.service_id else False,
            'hotline_transfer': self.hotline_transfer,
        }

        create_started = time.monotonic()
        lead = self.env['crm.lead'].with_context(
            default_source_id=False,
            ellaithy_popup_source_id=False,
            tracking_disable=True,
            mail_notrack=True,
            mail_create_nosubscribe=True,
        ).create(create_vals)

        _logger.info(
            "Create Opportunity timing: crm.lead.create %.3fs (lead=%s)",
            time.monotonic() - create_started,
            lead.id,
        )
        _logger.info(
            "Create Opportunity timing: TOTAL %.3fs (partner=%s lead=%s)",
            time.monotonic() - started,
            self.partner_id.id,
            lead.id,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Opportunity',
            'view_mode': 'form',
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'target': 'current',
        }

