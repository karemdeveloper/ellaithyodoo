from odoo import models, fields, api, _
from datetime import timedelta
import re
import logging

_logger = logging.getLogger(__name__)
EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    name = fields.Char(
        related='task_type_id.name',
        string='Subject',
        store=True,
        readonly=False
    )

    task_type_id = fields.Many2one('helpdesk.task.type', string="Task Type",
                                   domain="[('team_id', '=', team_id)]")

    equipment_task_type = fields.Many2one(related='task_type_id.equipment_id', string="Equipment")
    expected_duration = fields.Float(related='task_type_id.duration_hours', string="Duration (Hrs)", store=True)

    reminder_80_sent = fields.Boolean(default=False)
    overdue_hr_sent = fields.Boolean(default=False)

    team_manager_id = fields.Many2one(
        related='team_id.manager_id',
        string="Team Manager User",
        store=False
    )

    member_ids = fields.Many2many(related='team_id.member_ids')
    notes = fields.Text(string="Notes")
    team_leader_id = fields.Many2one(
        related='team_id.team_leader_id',
        string="Team Leader User",
        store=False
    )
    created_by_name = fields.Char(related='create_uid.name', string="Created By", store=True)
    date_last_escalation = fields.Datetime(string="Last Escalation Date")

    # dependency_ticket_id = fields.Many2one(
    #     'helpdesk.ticket',
    #     string="Blocked By",
    #     domain="[('id', '!=', id), ('stage_id.fold', '=', False)]" ,tracking=True)

    # hold_start_date = fields.Datetime(string="Hold Start Date", compute="_compute_hold_data", store=True,
    #                                   readonly=False)
    # total_hold_duration = fields.Float(string="Total Hold Time (Hours)", default=0.0, store=True)
    # pre_hold_stage_id = fields.Many2one('helpdesk.stage', string="Pre-Hold Stage")

    # @api.depends('dependency_ticket_id', 'dependency_ticket_id.stage_id.fold', 'stage_id')
    # def _compute_hold_data(self):
    #     all_stages = self.env['helpdesk.stage'].search([
    #         '|', '|',
    #         ('is_hold_stage', '=', True),
    #         ('is_default_return_stage', '=', True),
    #         ('fold', '=', False)
    #     ])
    #
    #     for ticket in self:
    #         is_blocked = ticket.dependency_ticket_id and not ticket.dependency_ticket_id.stage_id.fold
    #
    #         if is_blocked:
    #             if not ticket.hold_start_date:
    #                 ticket.hold_start_date = fields.Datetime.now()
    #                 _logger.info(">>> [Compute] Ticket %s is now ON-HOLD", ticket.id)
    #
    #                 target_hold_stage = all_stages.filtered(
    #                     lambda s: s.is_hold_stage and ticket.team_id in s.team_ids
    #                 )[:1]
    #
    #                 if target_hold_stage and ticket.stage_id != target_hold_stage:
    #                     ticket.stage_id = target_hold_stage.id
    #                     _logger.info(">>> Moved to Hold stage: %s", target_hold_stage.name)
    #
    #         elif ticket.hold_start_date:
    #             _logger.info(">>> [Compute] Dependency cleared for Ticket %s.", ticket.id)
    #
    #             ticket._update_hold_duration()
    #             ticket.hold_start_date = False
    #
    #             target_return_stage = all_stages.filtered(
    #                 lambda s: s.is_default_return_stage and ticket.team_id in s.team_ids
    #             )[:1]
    #
    #             if not target_return_stage:
    #                 target_return_stage = all_stages.filtered(
    #                     lambda s: not s.is_hold_stage
    #                               and not s.fold
    #                               and ticket.team_id in s.team_ids
    #                               and s.sequence > 1
    #                 ).sorted(key=lambda r: r.sequence)[:1]
    #
    #             if target_return_stage:
    #                 ticket.stage_id = target_return_stage.id
    #                 _logger.info(">>> Returned to stage: %s", target_return_stage.name)

    # def _update_hold_duration(self):
    #     now = fields.Datetime.now()
    #     for ticket in self:
    #         _logger.info(">>> [_update_hold_duration] Processing Ticket ID: %s", ticket.id)
    #         if ticket.hold_start_date:
    #             diff = now - ticket.hold_start_date
    #             diff_hours = diff.total_seconds() / 3600
    #             ticket.total_hold_duration += diff_hours
    #             _logger.info(">>> [_update_hold_duration] Added %s hours. New Total Hold: %s", diff_hours,
    #                          ticket.total_hold_duration)
    #             ticket.hold_start_date = False
    #         else:
    #             _logger.info(">>> [_update_hold_duration] No hold_start_date found, skipping.")

    @api.depends('team_id')
    def _compute_user_and_stage_ids(self):
        for ticket in self:

            if ticket.team_id and ticket.team_id.assign_method == 'manual':
                ticket.user_id = False
            else:
                if ticket.team_id and not ticket.user_id:
                    ticket.user_id = ticket.team_id._determine_user_to_assign()[ticket.team_id.id]

            if ticket.team_id:
                if not ticket.stage_id or ticket.stage_id not in ticket.team_id.stage_ids:
                    ticket.stage_id = ticket.team_id._determine_stage()[ticket.team_id.id]

    @api.onchange('team_id')
    def _onchange_team_id_clear_task_type(self):
        if self.team_id:
            self.task_type_id = False

    @api.onchange('task_type_id', 'team_id')
    def _onchange_task_type_responsible(self):
        if self.task_type_id and self.task_type_id.responsible_id:
            current_user_id = self.env.user.id
            is_manager = current_user_id == self.team_id.manager_id.id
            is_leader = current_user_id == self.team_id.team_leader_id.id

            if is_manager or is_leader:
                self.user_id = self.task_type_id.responsible_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('task_type_id'):
                task_type = self.env['helpdesk.task.type'].browse(vals['task_type_id'])
                if task_type.responsible_id:
                    vals['user_id'] = task_type.responsible_id.id

        tickets = super(HelpdeskTicket, self).create(vals_list)

        for ticket in tickets:
            if ticket.team_id:
                receivers = []
                if ticket.team_id.manager_id and ticket.team_id.manager_id.login:
                    receivers.append(ticket.team_id.manager_id.login)

                if ticket.team_id.team_leader_id and ticket.team_id.team_leader_id.login:
                    receivers.append(ticket.team_id.team_leader_id.login)

                valid_emails = [e for e in receivers if e and re.match(EMAIL_REGEX, e.strip())]

                if valid_emails:
                    email_list = ",".join(list(set(valid_emails)))

                    template = self.env.ref('ellithy_helpdesk.email_template_ticket_created_dept',
                                            raise_if_not_found=False)
                    if template:
                        template.sudo().with_context(email_to_all=email_list).send_mail(ticket.id, force_send=True)

        return tickets

    def write(self, vals):
        if 'user_id' in vals and vals['user_id']:
            _logger.info(">>> [Write] Assigning User ID %s to Tickets: %s", vals['user_id'], self.ids)
            template = self.env.ref('ellithy_helpdesk.email_template_ticket_assigned_member', raise_if_not_found=False)
            if template:
                for ticket in self:
                    template.send_mail(ticket.id, force_send=True)

        if 'stage_id' in vals:
            stage = self.env['helpdesk.stage'].browse(vals['stage_id'])
            _logger.info(">>> [Write] Stage Change Detected for Tickets %s. New Stage: %s", self.ids, stage.name)

            if stage.fold:
                template_ref = False
                if stage.name == 'Solved':
                    template_ref = 'ellithy_helpdesk.email_template_ticket_solved'
                elif stage.name == 'Cancelled':
                    template_ref = 'ellithy_helpdesk.email_template_ticket_cancelled'

                if template_ref:
                    template = self.env.ref(template_ref, raise_if_not_found=False)
                    if template:
                        for ticket in self:
                            template.send_mail(ticket.id, force_send=True)

        return super(HelpdeskTicket, self).write(vals)

    # def write(self, vals):
    #     if 'user_id' in vals and vals['user_id']:
    #         _logger.info(">>> [Write] Assigning User ID %s to Tickets: %s", vals['user_id'], self.ids)
    #         template = self.env.ref('ellithy_helpdesk.email_template_ticket_assigned_member', raise_if_not_found=False)
    #         if template:
    #             for ticket in self:
    #                 template.send_mail(ticket.id, force_send=True)
    #
    #     if 'stage_id' in vals:
    #         stage = self.env['helpdesk.stage'].browse(vals['stage_id'])
    #         _logger.info(">>> [Write] Stage Change Detected for Tickets %s. New Stage: %s (Folded: %s)",
    #                      self.ids, stage.name, stage.fold)
    #
    #         if stage.fold:
    #             _logger.info(">>> [Write] Stage is Folded. Checking for blocked tickets to release.")
    #
    #             blocked_tickets = self.env['helpdesk.ticket'].search([('dependency_ticket_id', 'in', self.ids)])
    #
    #             if blocked_tickets:
    #                 _logger.info(">>> [Write] Releasing %s blocked tickets.", len(blocked_tickets))
    #
    #                 blocked_tickets._update_hold_duration()
    #
    #                 blocked_tickets._compute_hold_data()
    #
    #             template_ref = False
    #             if stage.name == 'Solved':
    #                 template_ref = 'ellithy_helpdesk.email_template_ticket_solved'
    #             elif stage.name == 'Cancelled':
    #                 template_ref = 'ellithy_helpdesk.email_template_ticket_cancelled'
    #
    #             if template_ref:
    #                 template = self.env.ref(template_ref, raise_if_not_found=False)
    #                 if template:
    #                     for ticket in self:
    #                         template.send_mail(ticket.id, force_send=True)
    #
    #     return super(HelpdeskTicket, self).write(vals)

    def action_ticket_sla_cron(self):
        _logger.info(">>> [Cron SLA] Starting Simple SLA & Escalation Checker at %s", fields.Datetime.now())
        now = fields.Datetime.now()

        hr_team = self.env['helpdesk.team'].search([('name', 'ilike', 'HR')], limit=1)
        hr_emails_list = ",".join(hr_team.member_ids.mapped('login')) if hr_team and hr_team.member_ids else False

        tickets = self.search([
            ('stage_id.fold', '=', False),
            ('task_type_id', '!=', False),
            ('expected_duration', '>', 0)
        ])

        all_escalation_stages = self.env['helpdesk.stage'].search([('is_escalation_stage', '=', True)])

        for ticket in tickets:
            original_duration = ticket.expected_duration
            current_esc_level = ticket.stage_id.escalation_level or 'none'

            effective_time = (now - ticket.create_date).total_seconds() / 3600


            if current_esc_level == 'none':
                if not ticket.reminder_80_sent and effective_time >= (original_duration * 0.8):
                    self._send_sla_reminder_80(ticket, effective_time)

                if effective_time > original_duration:
                    target_stage = all_escalation_stages.filtered(
                        lambda s: s.escalation_level == 'leader' and ticket.team_id in s.team_ids
                    )[:1]

                    if target_stage and ticket.team_id.team_leader_id:
                        ticket.write({
                            'stage_id': target_stage.id,
                            'user_id': ticket.team_id.team_leader_id.id,
                            'date_last_escalation': now
                        })
                        template = self.env.ref('ellithy_helpdesk.email_template_escalation_leader',
                                                raise_if_not_found=False)
                        if template:
                            template.sudo().send_mail(ticket.id, force_send=True)
                        _logger.info(">>> Ticket %s escalated to LEADER due to SLA breach", ticket.name)

            elif current_esc_level == 'leader' and ticket.date_last_escalation:
                time_in_stage = (now - ticket.date_last_escalation).total_seconds() / 3600

                if time_in_stage > (original_duration * 0.5):
                    target_stage = all_escalation_stages.filtered(
                        lambda s: s.escalation_level == 'manager' and ticket.team_id in s.team_ids
                    )[:1]

                    if target_stage and ticket.team_id.manager_id:
                        ticket.write({
                            'stage_id': target_stage.id,
                            'user_id': ticket.team_id.manager_id.id,
                            'date_last_escalation': now
                        })
                        template = self.env.ref('ellithy_helpdesk.email_template_escalation_manager',
                                                raise_if_not_found=False)
                        if template:
                            template.sudo().send_mail(ticket.id, force_send=True)
                        _logger.info(">>> Ticket %s escalated to MANAGER", ticket.name)

            elif current_esc_level == 'manager' and ticket.date_last_escalation:
                time_in_stage = (now - ticket.date_last_escalation).total_seconds() / 3600

                if time_in_stage > (original_duration * 0.5) and not ticket.overdue_hr_sent:
                    if hr_emails_list:
                        template = self.env.ref('ellithy_helpdesk.email_template_overdue_hr', raise_if_not_found=False)
                        if template:
                            template.sudo().with_context(hr_email=hr_emails_list).send_mail(ticket.id, force_send=True)
                            ticket.overdue_hr_sent = True
                            _logger.info(">>> FINAL SLA BREACH: HR Alert sent for %s", ticket.name)

        _logger.info(">>> [Cron SLA] Job Completed.")
        return True

    # def action_ticket_sla_cron(self):
    #     _logger.info(">>> [Cron SLA] Starting Advanced SLA & Escalation Checker at %s", fields.Datetime.now())
    #     now = fields.Datetime.now()
    #
    #     hr_team = self.env['helpdesk.team'].search([('name', 'ilike', 'HR')], limit=1)
    #     hr_emails_list = ",".join(hr_team.member_ids.mapped('login')) if hr_team and hr_team.member_ids else False
    #
    #     tickets = self.search([
    #         ('stage_id.fold', '=', False),
    #         ('task_type_id', '!=', False),
    #         ('expected_duration', '>', 0)
    #     ])
    #
    #     all_escalation_stages = self.env['helpdesk.stage'].search([('is_escalation_stage', '=', True)])
    #
    #     for ticket in tickets:
    #         original_duration = ticket.expected_duration
    #         current_esc_level = ticket.stage_id.escalation_level or 'none'
    #
    #         total_passed_hours = (now - ticket.create_date).total_seconds() / 3600
    #         current_hold_segment = (
    #                                            now - ticket.hold_start_date).total_seconds() / 3600 if ticket.hold_start_date else 0
    #         effective_time = total_passed_hours - (ticket.total_hold_duration + current_hold_segment)
    #
    #         if current_esc_level == 'none':
    #             if not ticket.reminder_80_sent and effective_time >= (original_duration * 0.8):
    #                 if not ticket.hold_start_date:
    #                     self._send_sla_reminder_80(ticket, effective_time)
    #
    #             if effective_time > original_duration and not ticket.hold_start_date:
    #                 target_stage = all_escalation_stages.filtered(
    #                     lambda s: s.escalation_level == 'leader' and ticket.team_id in s.team_ids
    #                 )[:1]
    #
    #                 if target_stage and ticket.team_id.team_leader_id:
    #                     ticket.write({
    #                         'stage_id': target_stage.id,
    #                         'user_id': ticket.team_id.team_leader_id.id,
    #                         'date_last_escalation': now
    #                     })
    #                     template = self.env.ref('ellithy_helpdesk.email_template_escalation_leader',
    #                                             raise_if_not_found=False)
    #                     if template:
    #                         template.sudo().send_mail(ticket.id, force_send=True)
    #                     _logger.info(">>> Ticket %s escalated to LEADER (Stage: %s)", ticket.name, target_stage.name)
    #
    #         elif current_esc_level == 'leader' and ticket.date_last_escalation:
    #             time_in_stage = (now - ticket.date_last_escalation).total_seconds() / 3600
    #
    #             if time_in_stage > (original_duration * 0.5) and not ticket.hold_start_date:
    #                 target_stage = all_escalation_stages.filtered(
    #                     lambda s: s.escalation_level == 'manager' and ticket.team_id in s.team_ids
    #                 )[:1]
    #
    #                 if target_stage and ticket.team_id.manager_id:
    #                     ticket.write({
    #                         'stage_id': target_stage.id,
    #                         'user_id': ticket.team_id.manager_id.id,
    #                         'date_last_escalation': now
    #                     })
    #                     template = self.env.ref('ellithy_helpdesk.email_template_escalation_manager',
    #                                             raise_if_not_found=False)
    #                     if template:
    #                         template.sudo().send_mail(ticket.id, force_send=True)
    #                     _logger.info(">>> Ticket %s escalated to MANAGER (Stage: %s)", ticket.name, target_stage.name)
    #
    #         elif current_esc_level == 'manager' and ticket.date_last_escalation:
    #             time_in_stage = (now - ticket.date_last_escalation).total_seconds() / 3600
    #
    #             if time_in_stage > (original_duration * 0.5) and not ticket.overdue_hr_sent:
    #                 if not ticket.hold_start_date and hr_emails_list:
    #                     template = self.env.ref('ellithy_helpdesk.email_template_overdue_hr', raise_if_not_found=False)
    #                     if template:
    #                         template.sudo().with_context(hr_email=hr_emails_list).send_mail(ticket.id, force_send=True)
    #                         ticket.overdue_hr_sent = True
    #                         _logger.info(">>> FINAL SLA BREACH: HR Alert sent for %s", ticket.name)
    #
    #     _logger.info(">>> [Cron SLA] Job Completed.")
    #     return True

    def _send_sla_reminder_80(self, ticket, effective_time):

        receivers = []
        if ticket.team_id.manager_id.login:
            receivers.append(ticket.team_id.manager_id.login)
        if ticket.team_id.team_leader_id.login:
            receivers.append(ticket.team_id.team_leader_id.login)
        if ticket.user_id.login:
            receivers.append(ticket.user_id.login)

        valid_receivers = list(set([e for e in receivers if e and re.match(EMAIL_REGEX, e.strip())]))

        if valid_receivers:
            team_emails = ",".join(valid_receivers)
            template = self.env.ref('ellithy_helpdesk.email_template_reminder_80', raise_if_not_found=False)

            if template:
                remaining_hours = round(ticket.expected_duration - effective_time, 2)

                template.sudo().with_context(
                    team_emails_all=team_emails,
                    remaining_hours=remaining_hours
                ).send_mail(ticket.id, force_send=True)

                ticket.reminder_80_sent = True

    # def _send_sla_reminder_80(self, ticket, effective_time):
    #     if ticket.hold_start_date:
    #         return
    #
    #     receivers = []
    #     if ticket.team_id.manager_id.login:
    #         receivers.append(ticket.team_id.manager_id.login)
    #     if ticket.team_id.team_leader_id.login:
    #         receivers.append(ticket.team_id.team_leader_id.login)
    #     if ticket.user_id.login:
    #         receivers.append(ticket.user_id.login)
    #
    #     valid_receivers = list(set([e for e in receivers if e and re.match(EMAIL_REGEX, e.strip())]))
    #
    #     if valid_receivers:
    #         team_emails = ",".join(valid_receivers)
    #         template = self.env.ref('ellithy_helpdesk.email_template_reminder_80', raise_if_not_found=False)
    #
    #         if template:
    #             remaining_hours = round(ticket.expected_duration - effective_time, 2)
    #
    #             template.sudo().with_context(
    #                 team_emails_all=team_emails,
    #                 remaining_hours=remaining_hours
    #             ).send_mail(ticket.id, force_send=True)
    #
    #             ticket.reminder_80_sent = True


