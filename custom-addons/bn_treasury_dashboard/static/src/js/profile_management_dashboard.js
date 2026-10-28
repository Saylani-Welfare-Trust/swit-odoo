/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ProfileManagementDashboard extends Component {
    setup() {
        this.orm = useService('orm');
        this.actionService = useService("action");

        this.state = useState({
            date_from: '',
            date_to: '',
            active_tab: 'pos', // Default tab
            kpi: {
                registered: 0, draft: 0, rejected: 0,
                donors: 0, donees: 0, individuals: 0,
            },
            chart_regs: { labels: [], data: [] },
            chart_cats: { labels: [], data: [] },
            recent_registrations: [],
            recent_drafts: [],
            // Tab data
            pos_orders: [],
            boxes: [],
            home_services: [],
            imports: [],
            online: [],
            in_kind: [],
        });

        this._charts = {};
        this.is_mounted = false;

        onWillStart(async () => {
            await this.fetch_data();
        });

        onMounted(() => {
            this.is_mounted = true;
            this.render_charts();
        });
    }

    async fetch_data() {
        try {
            const data = await this.orm.call('profile.management.dashboard', 'get_dashboard_data', [
                this.state.date_from || null,
                this.state.date_to || null,
            ]);
            
            this.state.kpi = data.kpi;
            this.state.chart_regs = data.chart_regs;
            this.state.chart_cats = data.chart_cats;
            this.state.recent_registrations = data.recent_registrations;
            this.state.recent_drafts = data.recent_drafts;
            this.state.pos_orders = data.pos_orders;
            this.state.boxes = data.boxes;
            this.state.home_services = data.home_services;
            this.state.imports = data.imports;
            this.state.online = data.online;
            this.state.in_kind = data.in_kind;
        } catch (error) {
            console.error("Dashboard Fetch Error:", error);
        }

        if (this.is_mounted) {
            this.render_charts();
        }
    }

    async applyFilter() {
        await this.fetch_data();
    }

    setTab(tab) {
        this.state.active_tab = tab;
    }

    clearFilter() {
        this.state.date_from = '';
        this.state.date_to = '';
        this.applyFilter();
    }

    setQuickDate(type) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const month = today.getMonth();

        const fmt = (d) => {
            const y = d.getFullYear();
            const m = String(d.getMonth() + 1).padStart(2, '0');
            const dd = String(d.getDate()).padStart(2, '0');
            return `${y}-${m}-${dd}`;
        };

        if (type === 'this_month') {
            this.state.date_from = fmt(new Date(yyyy, month, 1));
            this.state.date_to = fmt(new Date(yyyy, month + 1, 0));
        } else if (type === 'last_month') {
            this.state.date_from = fmt(new Date(yyyy, month - 1, 1));
            this.state.date_to = fmt(new Date(yyyy, month, 0));
        } else if (type === 'this_year') {
            this.state.date_from = `${yyyy}-01-01`;
            this.state.date_to = `${yyyy}-12-31`;
        }
        this.applyFilter();
    }

    render_charts() {
        const ctx1 = $("#pm_chart_regs");
        if (ctx1.length) {
            if (this._charts.regs) this._charts.regs.destroy();
            this._charts.regs = new Chart(ctx1, {
                type: 'bar',
                data: {
                    labels: this.state.chart_regs.labels,
                    datasets: [{
                        label: 'Registrations',
                        data: this.state.chart_regs.data,
                        backgroundColor: "rgba(75, 192, 192, 0.8)",
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        const ctx2 = $("#pm_chart_cats");
        if (ctx2.length) {
            if (this._charts.cats) this._charts.cats.destroy();
            this._charts.cats = new Chart(ctx2, {
                type: 'doughnut',
                data: {
                    labels: this.state.chart_cats.labels,
                    datasets: [{
                        data: this.state.chart_cats.data,
                        backgroundColor: ["#4bc0c0", "#36a2eb", "#ff6384", "#ffce56", "#cc65fe", "#ff9f40"],
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }
            });
        }
    }

    formatStateName(stateName) {
        if (!stateName) return '';
        return stateName.charAt(0).toUpperCase() + stateName.slice(1).replace(/_/g, ' ');
    }

    getStateColor(stateName) {
        if (!stateName) return 'bg-secondary';
        const s = stateName.toLowerCase();
        if (['register', 'available', 'paid', 'done'].includes(s)) return 'bg-success';
        if (['draft', 'pending'].includes(s)) return 'bg-warning text-dark';
        if (['reject', 'rejected', 'cancel'].includes(s)) return 'bg-danger';
        return 'bg-info text-white';
    }
    
    openView(model, domain = []) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: model,
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current'
        });
    }
}

ProfileManagementDashboard.template = 'ProfileManagementDashboard';
registry.category("actions").add("profile_management_dashboard", ProfileManagementDashboard);