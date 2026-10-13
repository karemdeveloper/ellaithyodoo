/** @odoo-module **/
import { Component, onWillStart, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

export class MarketingDashboard extends Component {
    static template = 'ellaithy_marketing_python.MarketingDashboard';
    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
        const now = new Date();
        const first = new Date(now.getFullYear(), now.getMonth(), 1);
        const fmt = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
        this.state = useState({ loading: false, filters: {}, result: null, date_from: fmt(first), date_to: fmt(now),
            company_id: '', source_id: '', campaign_id: '', team_id: '', user_id: '', stage_id: '', lead_type: '', group_by: 'source' });
        onWillStart(async () => {
            try { this.state.filters = await this.orm.call('ellaithy.marketing.dashboard', 'get_filters', []); await this.refresh(); }
            catch (error) { this.notification.add(error.message || 'Unable to load marketing analytics', {type: 'danger'}); }
        });
    }
    async refresh() {
        this.state.loading = true;
        try {
            const args = {};
            for (const key of ['date_from','date_to','company_id','source_id','campaign_id','team_id','user_id','stage_id','lead_type','group_by']) {
                if (this.state[key]) args[key] = this.state[key];
            }
            this.state.result = await this.orm.call('ellaithy.marketing.dashboard', 'get_dashboard', [], args);
        } catch (error) { this.notification.add(error.message || 'Marketing analytics could not be loaded', {type:'danger'}); }
        finally { this.state.loading = false; }
    }
    setFilter(ev, key) { this.state[key] = ev.target.value; }
    max(rows, field) { return Math.max(1, ...(rows || []).map(r => Number(r[field] || 0))); }
    width(value, maximum) { return `${Math.min(100, Math.max(0, Number(value || 0) / maximum * 100))}%`; }
    number(value) { return Number(value || 0).toLocaleString(undefined, {maximumFractionDigits:2}); }
}
registry.category('actions').add('ellaithy_marketing_python.dashboard', MarketingDashboard);
