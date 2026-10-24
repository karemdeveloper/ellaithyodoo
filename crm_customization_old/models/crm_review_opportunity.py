from odoo import models, fields, api
from datetime import timedelta


class CrmReviewOpportunity(models.Model):
    _name = 'crm.review.opportunity'
    _description = 'Review Opportunities and Inactive Hours'
    _rec_name = 'branch_id'

    branch_id = fields.Many2one(
        'res.branch',
        string='Branch',
        required=True
    )

    salesperson_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        help='Optional: filter opportunities by a specific salesperson'
    )

    line_ids = fields.One2many(
        'crm.review.opportunity.line',
        'review_id',
        string='Salesperson Lines'
    )
    date_from = fields.Datetime(string="Date From")
    date_to = fields.Datetime(string="Date To")

    def action_load_opportunities(self):
        """
        Load opportunities grouped by salesperson.
        One line per salesperson, containing all related opportunities.
        """
        self.ensure_one()
        self.line_ids.unlink()  # Clear previous lines

        # Domain to filter crm.lead
        domain = [
            ('branch_name', '=', self.branch_id.id),
            ('user_id', '!=', False),
        ]

        if self.salesperson_id:
            domain.append(('user_id', '=', self.salesperson_id.id))
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))

        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        print(f"[CRM Review] Searching Leads with domain: {domain}")

        leads = self.env['crm.lead'].search(domain)
        print(f"[CRM Review] Found {len(leads)} leads")

        for lead in leads:
            print(f"Lead: {lead.name}, Salesperson: {lead.user_id.name}, Branch: {lead.branch_name.branch_name}")

        # Group leads by salesperson
        grouped = {}
        for lead in leads:
            grouped.setdefault(lead.user_id, self.env['crm.lead'])
            grouped[lead.user_id] |= lead

        print(f"[CRM Review] Grouped Salespersons: {[u.name for u in grouped.keys()]}")

        # Create one line per salesperson
        for salesperson, opps in grouped.items():
            print(f"Creating line for {salesperson.name} with {len(opps)} opportunities")
            self.env['crm.review.opportunity.line'].create({
                'review_id': self.id,
                'salesperson_id': salesperson.id,
                'opportunity_ids': [(6, 0, opps.ids)],  # Set Many2many
            })


class CrmReviewOpportunityLine(models.Model):
    _name = 'crm.review.opportunity.line'
    _description = 'Review Opportunity Line (Per Salesperson)'

    # ==============================
    # RELATION FIELDS
    # ==============================
    review_id = fields.Many2one(
        'crm.review.opportunity',
        string='Review',
        ondelete='cascade'
    )

    salesperson_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        required=True
    )

    # Many2many to store opportunities for this salesperson
    opportunity_ids = fields.Many2many(
        'crm.lead',
        'crm_review_opportunity_lead_rel',
        'line_id',
        'lead_id',
        string='Opportunities',
        readonly=True
    )

    # Compute total inactive hours for this salesperson
    inactive_hours = fields.Float(
        string='Inactive Hours',
        compute='_compute_inactive_hours',
        store=False
    )
    # field to compute opportunity_number
    opportunity_number = fields.Integer(
        string='Opportunities Count',
        compute='_compute_opportunity_number',
        store=False
    )


    # ==============================
    # COMPUTE METHODS
    # ==============================
    @api.depends('opportunity_ids')
    def _compute_opportunity_number(self):
        for rec in self:
            rec.opportunity_number = len(rec.opportunity_ids)

    ################################
    def _compute_inactive_hours(self):
        """
        Sum inactive hours for the salesperson
        considering overlap with review date range
        """
        for rec in self:
            total_seconds = 0.0

            review_from = rec.review_id.date_from
            review_to = rec.review_id.date_to

            requests = self.env['inactive.request'].search([
                ('salesperson_id', '=', rec.salesperson_id.id),
                ('state', '=', 'approved'),
                ('date_from', '!=', False),
                ('date_to', '!=', False),
            ])

            for req in requests:
                req_from = req.date_from
                req_to = req.date_to

                # if not review range
                if not review_from and not review_to:
                    overlap_start = req_from
                    overlap_end = req_to
                else:
                    overlap_start = max(req_from, review_from) if review_from else req_from
                    overlap_end = min(req_to, review_to) if review_to else req_to

                # check overlap
                if overlap_start < overlap_end:
                    delta = overlap_end - overlap_start
                    total_seconds += delta.total_seconds()

                    print(
                        f"[Inactive Overlap] Salesperson: {rec.salesperson_id.name}, "
                        f"Request: {req.inactive_reason.name}, "
                       f"[Inactive Overlap] {req.date_from} → {req.date_to} | "
                        f"Overlap Hours: {delta.total_seconds() / 3600:.2f}"
                    )

                print(req_from, req_to, overlap_start, overlap_end, 'wwwwwwwwwwwwwwwwwwwwww')
            rec.inactive_hours = round(total_seconds / 3600, 2)

            print(
                f"[Inactive] Total inactive hours for {rec.salesperson_id.name}: "
                f"{rec.inactive_hours}"
            )
