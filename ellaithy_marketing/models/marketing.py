from collections import defaultdict
from datetime import date, datetime, timedelta
from calendar import monthrange

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MarketingCost(models.Model):
    _name = 'ellaithy.marketing.cost'
    _description = 'Marketing Cost'
    _order = 'year desc, month desc, id desc'

    name = fields.Char(required=True)
    source_id = fields.Many2one('utm.source', string='Marketing Source', ondelete='restrict')
    source_name = fields.Char(string='Source Label')
    campaign_id = fields.Many2one('utm.campaign', string='Campaign')
    platform = fields.Char(required=True, default='Other')
    year = fields.Integer(required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection([(str(i), date(2000, i, 1).strftime('%B')) for i in range(1, 13)], required=True,
                             default=lambda self: str(fields.Date.today().month))
    amount = fields.Monetary(required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    notes = fields.Text()

    @api.constrains('year', 'amount')
    def _check_values(self):
        for record in self:
            if record.year < 2000 or record.year > 2200:
                raise ValidationError(_('Year must be between 2000 and 2200.'))
            if record.amount < 0:
                raise ValidationError(_('Marketing cost cannot be negative.'))


class MarketingSourceGroup(models.Model):
    _name = 'ellaithy.marketing.source.group'
    _description = 'Marketing Source Merge Group'
    _order = 'name'

    name = fields.Char(required=True)
    source_ids = fields.Many2many('utm.source', string='Sources')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)


class MarketingSettings(models.Model):
    _name = 'ellaithy.marketing.settings'
    _description = 'Marketing Analytics Settings'

    name = fields.Char(required=True, default='Default')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    branch_field_id = fields.Many2one('ir.model.fields', domain="[('model','=','crm.lead'),('ttype','in',['char','selection','many2one'])]", string='CRM Branch Field')
    source_field_id = fields.Many2one('ir.model.fields', domain="[('model','=','crm.lead'),('ttype','in',['char','selection','many2one'])]", string='CRM Source Field')
    profile_field_id = fields.Many2one('ir.model.fields', domain="[('model','=','crm.lead'),('ttype','in',['char','selection','many2one'])]", string='CRM Profile Field')
    exclude_walk_in = fields.Boolean(string='Exclude walk-ins from attributed won counts')
    walk_in_text = fields.Char(default='walk-in')


class MarketingDashboard(models.AbstractModel):
    _name = 'ellaithy.marketing.dashboard'
    _description = 'Marketing Analytics Dashboard API'

    @api.model
    def get_filters(self):
        company_ids = self.env.companies.ids
        return {
            'sources': self.env['utm.source'].search_read([], ['name'], limit=2000),
            'campaigns': self.env['utm.campaign'].search_read([], ['name'], limit=2000),
            'teams': self.env['crm.team'].search_read([], ['name'], limit=2000),
            'companies': self.env['res.company'].search_read([('id', 'in', company_ids)], ['name']),
            'users': self.env['res.users'].search_read([('share', '=', False)], ['name'], limit=2000),
            'stages': self.env['crm.stage'].search_read([], ['name', 'is_won']),
        }

    @api.model
    def get_dashboard(self, date_from=False, date_to=False, company_id=False, source_id=False,
                      campaign_id=False, team_id=False, user_id=False, stage_id=False, lead_type=False,
                      group_by='source', compare=False):
        today = fields.Date.context_today(self)
        start = fields.Date.to_date(date_from) if date_from else today.replace(day=1)
        end = fields.Date.to_date(date_to) if date_to else today
        if start > end:
            raise ValidationError(_('Start date must be before end date.'))
        allowed = self.env.companies.ids
        company = int(company_id) if company_id else self.env.company.id
        if company not in allowed:
            raise ValidationError(_('Selected company is not accessible.'))
        domain = [('create_date', '>=', fields.Datetime.to_string(datetime.combine(start, datetime.min.time()))),
                  ('create_date', '<', fields.Datetime.to_string(datetime.combine(end + timedelta(days=1), datetime.min.time()))),
                  ('company_id', 'in', [company, False])]
        for field, val in [('source_id', source_id), ('campaign_id', campaign_id), ('team_id', team_id),
                           ('user_id', user_id), ('stage_id', stage_id)]:
            if val:
                domain.append((field, '=', int(val)))
        if lead_type in ('lead', 'opportunity'):
            domain.append(('type', '=', lead_type))
        lead_model = self.env['crm.lead']
        settings = self.env['ellaithy.marketing.settings'].search([('company_id', '=', company)], limit=1)
        branch_field = settings.branch_field_id.name if settings.branch_field_id and settings.branch_field_id.name in lead_model._fields else 'team_id'
        source_field = settings.source_field_id.name if settings.source_field_id and settings.source_field_id.name in lead_model._fields else 'source_id'
        profile_field = settings.profile_field_id.name if settings.profile_field_id and settings.profile_field_id.name in lead_model._fields else False
        groups = self.env['ellaithy.marketing.source.group'].search([('company_id', '=', company)])
        merge = {source.id: group.name for group in groups for source in group.source_ids}
        leads = lead_model.search(domain)
        stats = defaultdict(lambda: {'leads': 0, 'won': 0, 'lost': 0})
        timeline = defaultdict(lambda: {'leads': 0, 'won': 0})
        source_counts = defaultdict(lambda: {'leads': 0, 'won': 0})
        branch_counts = defaultdict(lambda: {'leads': 0, 'won': 0})
        stage_counts = defaultdict(int)
        totals = {'leads': 0, 'won': 0, 'lost': 0, 'spend': 0, 'conversion': 0, 'cpl': 0, 'cost_per_won': 0}
        for lead in leads:
            won = bool(lead.stage_id.is_won)
            lost = not won and not lead.active and lead.probability == 0
            if settings.exclude_walk_in and profile_field and won:
                profile = lead[profile_field]
                if (settings.walk_in_text or 'walk-in').lower() in str(profile.display_name if hasattr(profile, 'display_name') else profile).lower():
                    won = False
            src = lead[source_field]
            source_name = src.display_name if hasattr(src, 'display_name') else str(src or 'Not entered')
            if source_field == 'source_id' and lead.source_id.id in merge:
                source_name = merge[lead.source_id.id]
            branch = lead[branch_field]
            branch_name = branch.display_name if hasattr(branch, 'display_name') else str(branch or 'Not entered')
            campaign = lead.campaign_id.display_name or 'Not entered'
            channel = lead.medium_id.display_name or 'Not entered'
            dimension = {'source': source_name, 'branch': branch_name, 'campaign': campaign,
                         'channel': channel, 'salesperson': lead.user_id.display_name or 'Unassigned',
                         'team': lead.team_id.display_name or 'Unassigned',
                         'stage': lead.stage_id.display_name or 'Not entered'}.get(group_by, source_name)
            for item in (stats[dimension], source_counts[source_name], branch_counts[branch_name]):
                item['leads'] += 1
                item['won'] += int(won)
            stats[dimension]['lost'] += int(lost)
            stage_counts[lead.stage_id.display_name or 'Not entered'] += 1
            day = fields.Datetime.to_datetime(lead.create_date).date().isoformat()
            timeline[day]['leads'] += 1
            timeline[day]['won'] += int(won)
            totals['leads'] += 1
            totals['won'] += int(won)
            totals['lost'] += int(lost)
        costs = self.env['ellaithy.marketing.cost'].search([('company_id', '=', company),
                        ('year', '>=', start.year), ('year', '<=', end.year)])
        spend_by_source = defaultdict(float)
        spend_by_platform = defaultdict(float)
        spend_by_month = defaultdict(float)
        for cost in costs:
            period = date(cost.year, int(cost.month), 1)
            period_end = date(cost.year, int(cost.month), monthrange(cost.year, int(cost.month))[1])
            if period > end or period_end < start:
                continue
            # Reporting currency is the selected company's currency; conversion uses the cost month's first day.
            amount = cost.currency_id._convert(cost.amount, self.env['res.company'].browse(company).currency_id,
                                               self.env['res.company'].browse(company), period)
            totals['spend'] += amount
            name = merge.get(cost.source_id.id) or cost.source_name or cost.source_id.display_name or 'Not entered'
            spend_by_source[name] += amount
            spend_by_platform[cost.platform or 'Other'] += amount
            spend_by_month[period.isoformat()[:7]] += amount
        totals['conversion'] = round(totals['won'] * 100 / totals['leads'], 2) if totals['leads'] else 0
        totals['cpl'] = round(totals['spend'] / totals['leads'], 2) if totals['leads'] else 0
        totals['cost_per_won'] = round(totals['spend'] / totals['won'], 2) if totals['won'] else 0
        def rank(mapping, key='leads'):
            return [{'name': k, **v} for k, v in sorted(mapping.items(), key=lambda kv: kv[1].get(key, 0), reverse=True)[:30]]
        return {
            'totals': totals, 'currency': self.env['res.company'].browse(company).currency_id.symbol,
            'by_dimension': rank(stats), 'by_source': rank(source_counts), 'by_branch': rank(branch_counts),
            'by_stage': [{'name': k, 'value': v} for k, v in sorted(stage_counts.items(), key=lambda kv: -kv[1])],
            'timeline': [{'name': k, **v} for k, v in sorted(timeline.items())],
            'spend_source': [{'name': k, 'value': round(v, 2)} for k, v in sorted(spend_by_source.items(), key=lambda kv: -kv[1])],
            'spend_platform': [{'name': k, 'value': round(v, 2)} for k, v in sorted(spend_by_platform.items(), key=lambda kv: -kv[1])],
            'spend_month': [{'name': k, 'value': round(v, 2)} for k, v in sorted(spend_by_month.items())],
            'date_from': start.isoformat(), 'date_to': end.isoformat(),
        }
