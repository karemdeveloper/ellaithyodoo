from odoo import models, fields, api
from datetime import datetime, time


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    # Override the date_deadline field to include time
    date_deadline = fields.Datetime(
        string='Due Date',
        required=True,
        index=True,
        default=fields.Datetime.now
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle datetime/date comparison issue"""
        # Call the original parent create but skip the datetime comparison
        # We'll handle notifications ourselves
        activities = super(models.Model, self).create(vals_list)

        # find partners related to responsible users, separate readable from unreadable
        if any(user != self.env.user for user in activities.user_id):
            user_partners = activities.user_id.partner_id
            readable_user_partners = user_partners._filtered_access('read')
        else:
            readable_user_partners = self.env.user.partner_id

        # when creating activities for other: send a notification to assigned user;
        if self.env.context.get('mail_activity_quick_update'):
            activities_to_notify = self.env['mail.activity']
        else:
            activities_to_notify = activities.filtered(lambda act: act.user_id != self.env.user)
        if activities_to_notify:
            to_sudo = activities_to_notify.filtered(lambda act: act.user_id.partner_id not in readable_user_partners)
            other = activities_to_notify - to_sudo
            to_sudo.sudo().action_notify()
            other.action_notify()

        # subscribe (batch by model and user to speedup)
        from collections import defaultdict
        for model, activity_data in activities._classify_by_model().items():
            per_user = defaultdict(set)
            for activity in activity_data['activities'].filtered(lambda act: act.user_id):
                per_user[activity.user_id].add(activity.res_id)
            for user, res_ids in per_user.items():
                pids = user.partner_id.ids if user.partner_id in readable_user_partners else user.sudo().partner_id.ids
                self.env[model].browse(res_ids).message_subscribe(partner_ids=pids)

        # send notifications about activity creation with datetime comparison
        today_datetime = fields.Datetime.to_datetime(
            datetime.combine(fields.Date.today(), time.max)
        )
        todo_activities = activities.filtered(
            lambda act: act.active and act.date_deadline and act.date_deadline <= today_datetime
        )
        if todo_activities:
            for user, user_activities in todo_activities.grouped('user_id').items():
                user._bus_send("mail.activity/updated", {"activity_created": True, "count_diff": len(user_activities)})

        return activities

    def unlink(self):
        """Override unlink to handle datetime/date comparison issue"""
        # Convert Date.today() to datetime for proper comparison
        today_datetime = fields.Datetime.to_datetime(
            datetime.combine(fields.Date.today(), time.max)
        )

        todo_activities = self.filtered(
            lambda act: act.active and act.date_deadline and act.date_deadline <= today_datetime
        )

        if todo_activities:
            for user, user_activities in todo_activities.grouped('user_id').items():
                user._bus_send("mail.activity/updated", {"activity_deleted": True, "count_diff": -len(user_activities)})

        # Call the grandparent's unlink (models.Model) to skip mail.activity's date comparison
        return super(models.Model, self).unlink()

