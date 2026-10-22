from odoo import models, fields, api
import pytz
import logging
import time

_logger = logging.getLogger(__name__)

class DistributeSequence(models.Model):
    _name = 'distribute.sequence'
    _description = 'Distribute Sequence'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence asc'
    _sequence = 'sequence'

    active = fields.Boolean(string="Active", default=True, tracking=True)
    sequence = fields.Integer(string="Sequence", default=0)
    sales_person = fields.Many2one('res.users', string='Sales Person')
    branch = fields.Many2one('res.branch', string='Branch')
    shift = fields.Many2one('res.shift', string='Shift')
    from_date = fields.Float(string="From", related='shift.from_date', readonly=True)
    to_date = fields.Float(string="To", related='shift.to_date', readonly=True)

    state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string="Status", default='active', tracking=True,compute='_compute_team_member_state', store=True)


    @api.depends('sales_person', 'sales_person.crm_team_member_ids.state')
    def _compute_team_member_state(self):
        for rec in self:
            member = self.env['crm.team.member'].search([('user_id', '=', rec.sales_person.id)], limit=1)
            rec.state = member.state if member else False

    @api.model
    def _get_next_salesperson_for_branch(self, branch_id):
        """
        Shared round-robin distribution logic.
        Returns the next res.users salesperson for the given branch,
        respecting current shift and active sequences.
        """
        salespersons = self._get_next_salespersons_for_branch(branch_id, 1)
        return salespersons[0] if salespersons else False

    @api.model
    def _get_next_salespersons_for_branch(self, branch_id, count):
        """
        Returns the next `count` salespersons in turn for the given branch,
        exactly as `count` successive calls to _get_next_salesperson_for_branch
        would, but saves the round-robin pointer only once: set_param() clears
        the whole registry cache, which is costly when done per lead.
        Returns an empty list when no salesperson is available.

        Used by:
          - res.users           (action_archive_and_redistribute)
        """
        if count < 1:
            return []
        branch = self.env['res.branch'].browse(branch_id)
        if not branch.exists():
            _logger.info("Branch id=%s not found.", branch_id)
            return []

        # 1. Get branch sales teams
        sales_teams = self.env['crm.team'].search(
            [('branch_name', '=', branch.id)])
        if not sales_teams:
            _logger.info("No sales teams found for branch %s.", branch.branch_name)
            return []

        # 2. Active team members
        active_members = self.env['crm.team.member'].search([
            ('crm_team_id', 'in', sales_teams.ids),
            ('state', '=', 'active'),
        ])
        if not active_members:
            return []

        # 3. Egypt local time
        utc_now = fields.Datetime.now()
        egypt_tz = pytz.timezone('Africa/Cairo')
        local_now = utc_now.replace(tzinfo=pytz.utc).astimezone(egypt_tz)
        current_hour = local_now.hour + local_now.minute / 60.0

        _logger.info("Current Egypt hour: %.4f", current_hour)

        # 4. All active sequences for this branch
        all_sequences = self.search([
            ('branch', '=', branch.id),
            ('state', '=', 'active'),
            ('sales_person', 'in', active_members.mapped('user_id').ids),
        ], order='sequence asc, id asc')

        if not all_sequences:
            _logger.info("No active sequences found for branch %s.", branch.branch_name)
            return []

        # 5. Shift filter (handles overnight shifts)
        def _is_in_shift(shift, hour):
            if not shift:
                return False
            if shift.from_date <= shift.to_date:
                return shift.from_date <= hour <= shift.to_date
            else:
                return hour >= shift.from_date or hour <= shift.to_date

        sequences = all_sequences.filtered(
            lambda s: _is_in_shift(s.shift, current_hour))

        fallback_mode = False
        current_shift = False

        if not sequences:
            _logger.info("No sequences for current shift → Fallback to all active sequences")
            sequences = all_sequences
            fallback_mode = True
        else:
            current_shift = sequences[0].shift

        # 6. Debug logging
        _logger.info("===================================================")
        if fallback_mode:
            _logger.info("📌 FALLBACK MODE (No active shift)")
        else:
            _logger.info("📌 CURRENT SHIFT: %s (ID=%s)",
                         current_shift.shift_name, current_shift.id)
        _logger.info("Branch: %s (ID=%s)", branch.branch_name, branch.id)
        _logger.info("🕒 Current Hour: %.2f", current_hour)
        for seq in sequences:
            _logger.info(
                "   ➜ SeqID=%s | Order=%s | Shift=%s | User=%s",
                seq.id, seq.sequence,
                seq.shift.shift_name if seq.shift else "NO SHIFT",
                seq.sales_person.name if seq.sales_person else "NO USER",
            )
        _logger.info("===================================================")

        # 7. Lock-safe round-robin ticket.
        #
        # The old implementation updated one shared ir.config_parameter row
        # inside the user's main transaction. Under concurrency that row can be
        # locked by another long transaction and make Create Opportunity wait
        # for minutes.
        #
        # v4 uses a tiny *independent* transaction that increments an atomic
        # counter and commits immediately. A hard 300ms lock timeout prevents
        # the interactive request from ever waiting on the round-robin pointer.
        if fallback_mode:
            counter_key = f'crm_rr_v4_{branch.id}_fallback'
        else:
            counter_key = f'crm_rr_v4_{branch.id}_{current_shift.id}'

        valid_sequences = sequences.filtered(
            lambda seq: seq.sales_person and seq.sales_person.active
        )
        if not valid_sequences:
            _logger.info("No active salesperson available for branch %s.", branch.branch_name)
            return []

        try:
            with self.env.registry.cursor() as rr_cr:
                rr_cr.execute("SET LOCAL lock_timeout = '300ms'")
                rr_cr.execute(
                    """
                    INSERT INTO ir_config_parameter
                        (key, value, create_uid, write_uid, create_date, write_date)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (key)
                    DO UPDATE SET
                        value = (
                            (CASE
                                WHEN ir_config_parameter.value ~ '^[0-9]+$'
                                THEN ir_config_parameter.value::bigint
                                ELSE -1
                             END) + %s
                        )::text,
                        write_uid = EXCLUDED.write_uid,
                        write_date = NOW()
                    RETURNING value
                    """,
                    [counter_key, str(count - 1), self.env.uid, self.env.uid, count],
                )
                row = rr_cr.fetchone()
                rr_cr.commit()
                end_ticket = int(row[0]) if row else count - 1
                start_ticket = end_ticket - count + 1
        except Exception as exc:
            # Never block opportunity creation because the distribution pointer
            # is busy. This fallback is used only when the 300ms lock limit is hit.
            _logger.warning(
                "Round-robin counter unavailable for %s (%s); using non-blocking fallback.",
                counter_key, exc,
            )
            start_ticket = time.time_ns()

        salespersons = []
        seq_count = len(valid_sequences)
        for offset in range(count):
            next_seq = valid_sequences[(start_ticket + offset) % seq_count]
            salespersons.append(next_seq.sales_person)

        _logger.info(
            "Selected %s salesperson(s) with non-blocking RR key %s; first=%s",
            len(salespersons), counter_key,
            salespersons[0].name if salespersons else 'NONE',
        )
        return salespersons