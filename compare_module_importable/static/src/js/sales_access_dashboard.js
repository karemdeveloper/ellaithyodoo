/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

export class SalesAccessDashboard extends Component {
    static template = "compare_module.SalesAccessDashboard";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        const now = new Date();
        this.state = useState({
            loading: true,
            periodMonths: 6,
            teamId: "all",
            userId: "all",
            data: null,
        });
        this.periodOptions = [[3, "Last 3 months"], [6, "Last 6 months"], [12, "Last 12 months"]];
        onWillStart(() => this.loadData());
    }

    currentCompanyId() {
        const contextCompany = session.user_context?.allowed_company_ids?.[0];
        const currentCompany = session.user_companies?.current_company;
        if (contextCompany) return Number(contextCompany);
        if (typeof currentCompany === "number") return currentCompany;
        if (currentCompany && typeof currentCompany === "object") {
            return Number(currentCompany.id || currentCompany.company_id || false) || false;
        }
        return false;
    }

    startDate(months) {
        const date = new Date();
        date.setDate(1);
        date.setHours(0, 0, 0, 0);
        date.setMonth(date.getMonth() - (months - 1));
        return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-01 00:00:00`;
    }

    monthKey(value) {
        const date = new Date(String(value).replace(" ", "T") + "Z");
        return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
    }

    monthLabel(key) {
        const [year, month] = key.split("-").map(Number);
        return new Intl.DateTimeFormat("en", { month: "short", year: "numeric" }).format(new Date(year, month - 1, 1));
    }

    display(value, fallback = "Not assigned") {
        if (Array.isArray(value)) return value[1] || fallback;
        if (value === false || value === null || value === undefined || value === "") return fallback;
        return String(value);
    }

    async loadData() {
        this.state.loading = true;
        try {
            const companyId = this.currentCompanyId();
            const domain = [["create_date", ">=", this.startDate(Number(this.state.periodMonths))]];
            if (companyId) domain.push(["company_id", "in", [companyId, false]]);

            const fields = [
                "name", "create_date", "date_deadline", "active", "type", "user_id", "team_id",
                "stage_id", "source_id", "expected_revenue", "probability", "company_id"
            ];
            const leads = await this.orm.searchRead("crm.lead", domain, fields, {
                limit: 100000,
                context: { active_test: false },
                order: "create_date asc",
            });

            const stages = await this.orm.searchRead("crm.stage", [], ["id", "name", "is_won", "sequence"], { limit: 1000, order: "sequence asc" });
            const stageMap = Object.fromEntries(stages.map(stage => [stage.id, stage]));
            const wonStageIds = new Set(stages.filter(stage => stage.is_won).map(stage => stage.id));

            const teamsMap = new Map();
            const usersMap = new Map();
            for (const lead of leads) {
                if (lead.team_id?.[0]) teamsMap.set(lead.team_id[0], lead.team_id[1]);
                if (lead.user_id?.[0]) usersMap.set(lead.user_id[0], lead.user_id[1]);
            }
            const teams = [...teamsMap.entries()].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name));
            const users = [...usersMap.entries()].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name));

            const filtered = leads.filter(lead => {
                const teamMatch = this.state.teamId === "all" || Number(this.state.teamId) === lead.team_id?.[0];
                const userMatch = this.state.userId === "all" || Number(this.state.userId) === lead.user_id?.[0];
                return teamMatch && userMatch;
            });

            const now = new Date();
            const isWon = lead => wonStageIds.has(lead.stage_id?.[0]);
            const isLost = lead => lead.active === false && !isWon(lead);
            const isOpen = lead => !isWon(lead) && !isLost(lead);
            const isOverdue = lead => {
                if (!isOpen(lead) || !lead.date_deadline) return false;
                const deadline = new Date(String(lead.date_deadline).slice(0, 10) + "T23:59:59");
                return deadline < now;
            };

            const won = filtered.filter(isWon);
            const lost = filtered.filter(isLost);
            const open = filtered.filter(isOpen);
            const overdue = filtered.filter(isOverdue);
            const expectedRevenue = open.reduce((sum, lead) => sum + Number(lead.expected_revenue || 0), 0);
            const weightedRevenue = open.reduce((sum, lead) => sum + Number(lead.expected_revenue || 0) * Number(lead.probability || 0) / 100, 0);
            const conversionRate = filtered.length ? won.length * 100 / filtered.length : 0;

            const monthKeys = [];
            const first = new Date();
            first.setDate(1);
            first.setMonth(first.getMonth() - (Number(this.state.periodMonths) - 1));
            for (let i = 0; i < Number(this.state.periodMonths); i++) {
                const date = new Date(first.getFullYear(), first.getMonth() + i, 1);
                monthKeys.push(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`);
            }
            const monthlyMap = Object.fromEntries(monthKeys.map(key => [key, { key, label: this.monthLabel(key), leads: 0, won: 0 }]));
            for (const lead of filtered) {
                const key = this.monthKey(lead.create_date);
                if (!monthlyMap[key]) continue;
                monthlyMap[key].leads++;
                if (isWon(lead)) monthlyMap[key].won++;
            }
            const monthly = monthKeys.map(key => monthlyMap[key]);
            const monthlyMax = Math.max(1, ...monthly.flatMap(row => [row.leads, row.won]));

            const aggregate = (getter, subset = filtered) => {
                const map = new Map();
                for (const lead of subset) {
                    const key = getter(lead);
                    const row = map.get(key) || { name: key, leads: 0, won: 0, open: 0, revenue: 0 };
                    row.leads++;
                    if (isWon(lead)) row.won++;
                    if (isOpen(lead)) {
                        row.open++;
                        row.revenue += Number(lead.expected_revenue || 0);
                    }
                    map.set(key, row);
                }
                return [...map.values()].map(row => ({
                    ...row,
                    conversion: row.leads ? row.won * 100 / row.leads : 0,
                })).sort((a, b) => b.leads - a.leads || a.name.localeCompare(b.name));
            };

            const stageRows = aggregate(lead => stageMap[lead.stage_id?.[0]]?.name || this.display(lead.stage_id, "No stage"));
            const sourceRows = aggregate(lead => this.display(lead.source_id, "Not entered")).slice(0, 12);
            const teamRows = aggregate(lead => this.display(lead.team_id, "No sales team"));
            const salespersonRows = aggregate(lead => this.display(lead.user_id, "Not assigned"));
            const stageMax = Math.max(1, ...stageRows.map(row => row.leads));
            const sourceMax = Math.max(1, ...sourceRows.map(row => row.leads));

            this.state.data = {
                teams,
                users,
                leads: filtered,
                metrics: {
                    total: filtered.length,
                    open: open.length,
                    won: won.length,
                    lost: lost.length,
                    overdue: overdue.length,
                    expectedRevenue,
                    weightedRevenue,
                    conversionRate,
                },
                monthly,
                monthlyMax,
                stageRows,
                stageMax,
                sourceRows,
                sourceMax,
                teamRows,
                salespersonRows,
                accessNote: "Data is restricted by the logged-in user's Odoo CRM access rules.",
            };
        } catch (error) {
            console.error("Sales access dashboard error", error);
            this.notification.add(error.message || "Could not load the sales dashboard.", { type: "danger" });
            this.state.data = null;
        } finally {
            this.state.loading = false;
        }
    }

    async applyFilters() {
        await this.loadData();
    }

    barHeight(value) {
        return `${Math.max(3, Math.round((Number(value || 0) / (this.state.data?.monthlyMax || 1)) * 100))}%`;
    }

    barWidth(value, max) {
        return `${Math.max(value ? 3 : 0, Math.round((Number(value || 0) / (max || 1)) * 100))}%`;
    }

    formatNumber(value) {
        return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Number(value || 0));
    }

    formatMoney(value) {
        return new Intl.NumberFormat("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(value || 0));
    }

    formatPercent(value) {
        return `${Number(value || 0).toFixed(1)}%`;
    }
}

registry.category("actions").add("compare_module_importable.SalesAccessDashboard", SalesAccessDashboard);
