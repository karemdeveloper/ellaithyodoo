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
        """Use the shared, optimized round-robin distributor."""
        self.ensure_one()
        if not self.branch_id:
            return False
        return self.env['distribute.sequence']._get_next_salesperson_for_branch(
            self.branch_id.id
        )

    def action_distribute(self):
        """Create and assign an opportunity without expensive duplicate work."""
        self.ensure_one()
        started = time.monotonic()

        if not self.partner_id:
            raise ValidationError(_("Customer is required."))

        # crm.lead.create() is the single enforcement point for the
        # one-open-opportunity rule. Do not perform the same CRM query twice.

        salesperson = False
        if self.partner_id.user_id and self.partner_id.user_id.active:
            salesperson = self.partner_id.user_id
            _logger.info(
                "Create Opportunity: reused salesperson %s for partner %s",
                salesperson.id, self.partner_id.id,
            )
        else:
            assign_started = time.monotonic()
            salesperson = self._get_next_salesperson()
            _logger.info(
                "Create Opportunity timing: salesperson selection %.3fs",
                time.monotonic() - assign_started,
            )

        create_vals = {
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
            # Protect against the popup context being interpreted as the
            # native crm.lead.source_id (utm.source).
            default_source_id=False,
            ellaithy_popup_source_id=False,
        ).create(create_vals)
        _logger.info(
            "Create Opportunity timing: crm.lead.create %.3fs (lead=%s)",
            time.monotonic() - create_started, lead.id,
        )

        # Best-effort customer salesperson synchronization.
        #
        # This update is NOT required for the newly-created opportunity itself.
        # Give it only 250ms to obtain any PostgreSQL lock. If the customer row
        # is busy, skip the sync and return the opportunity immediately.
        if salesperson and self.partner_id.user_id.id != salesperson.id:
            partner_started = time.monotonic()
            try:
                with self.env.cr.savepoint():
                    self.env.cr.execute("SET LOCAL lock_timeout = '250ms'")
                    self.partner_id.with_context(
                        tracking_disable=True,
                        mail_notrack=True,
                        mail_create_nosubscribe=True,
                    ).write({'user_id': salesperson.id})
                self.env.cr.execute("SET LOCAL lock_timeout = '0'")
                _logger.info(
                    "Create Opportunity timing: partner salesperson sync %.3fs",
                    time.monotonic() - partner_started,
                )
            except Exception as exc:
                # A locked/busy partner must never block or fail lead creation.
                try:
                    self.env.cr.execute("SET LOCAL lock_timeout = '0'")
                except Exception:
                    pass
                _logger.warning(
                    "Create Opportunity: skipped partner salesperson sync after %.3fs: %s",
                    time.monotonic() - partner_started,
                    exc,
                )

        _logger.info(
            "Create Opportunity timing: TOTAL %.3fs (partner=%s lead=%s)",
            time.monotonic() - started, self.partner_id.id, lead.id,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Opportunity',
            'view_mode': 'form',
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'target': 'current',
        }

