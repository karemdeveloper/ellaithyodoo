from odoo import models, fields, api
import pytz
import logging

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

        # 7. Param key for round-robin pointer
        if fallback_mode:
            param_key = f'last_sequence_id_{branch.id}_fallback'
        else:
            param_key = f'last_sequence_id_{branch.id}_{current_shift.id}'

        config = self.env['ir.config_parameter'].sudo()
        last_seq_id_str = config.get_param(param_key)

        try:
            last_seq_id = int(last_seq_id_str) if last_seq_id_str else None
        except (TypeError, ValueError):
            last_seq_id = None

        valid_ids = sequences.ids

        salespersons = []
        for _turn in range(count):
            # 8. Round Robin
            if last_seq_id in valid_ids:
                current_index = valid_ids.index(last_seq_id)
                next_index = (current_index + 1) % len(valid_ids)
                next_seq = sequences[next_index]
            else:
                next_seq = sequences[0]

            # 8b. Archived salesperson → next one in turn takes it
            if not next_seq.sales_person.active:
                start = valid_ids.index(next_seq.id)
                for offset in range(1, len(valid_ids)):
                    candidate = sequences[(start + offset) % len(valid_ids)]
                    if candidate.sales_person.active:
                        _logger.info("Salesperson %s is archived → turn goes to %s",
                                     next_seq.sales_person.name, candidate.sales_person.name)
                        next_seq = candidate
                        break
                else:
                    _logger.info("All salespersons in the sequences are archived.")
                    return []

            # 9. Safety check
            if not next_seq.sales_person:
                _logger.warning("Sequence %s has no salesperson → searching alternative",
                                next_seq.id)
                for seq in sequences:
                    if seq.sales_person:
                        next_seq = seq
                        break
                else:
                    return []

            salespersons.append(next_seq.sales_person)
            last_seq_id = next_seq.id

        # 10. Save pointer (once for the whole batch)
        config.set_param(param_key, str(last_seq_id))

        _logger.info(
            "✅ Selected %s salesperson(s), last: %s (seq id=%s) → Saved param key %s",
            len(salespersons), next_seq.sales_person.name, next_seq.id, param_key
        )

        return salespersons