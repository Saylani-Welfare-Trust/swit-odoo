/** @odoo-module **/
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser"; 
import { Component, onWillStart, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const FILTER_STORAGE_KEY = 'profile_management_dashboard_filters';

export class ProfileManagementDashboard extends Component {
    setup() {
        this.orm = useService('orm');
        this.actionService = useService("action");

        let savedFilters = {};
        const rawFilters = browser.sessionStorage.getItem(FILTER_STORAGE_KEY);
        if (rawFilters) {
            try { savedFilters = JSON.parse(rawFilters); } catch (e) {}
        }

        this.state = useState({
            date_from: savedFilters.date_from || '',
            date_to: savedFilters.date_to || '',
            active_tab: savedFilters.active_tab || 'pos',
            kpi: { registered: 0, draft: 0, rejected: 0, donors: 0, donees: 0, individuals: 0 },
            chart_regs: { labels: [], data: [] },
            chart_cats: { labels: [], data: [] },
            recent_registrations: [],
            recent_drafts: [],
            
            // Donors
            pos_top_donors: [],
            box_top_donors: [],
            home_top_donors: [],
            import_top_donors: [],
            online_top_donors: [],
            in_kind_top_donors: [],
            
            // Donees
            welfare_top_donees: [],
            microfinance_top_donees: [],
            medical_top_donees: [],
        });

        this._charts = {};
        this.is_mounted = false;

        onWillStart(async () => { await this.fetch_data(); });
        onMounted(() => {
            this.is_mounted = true;
            this.render_charts();
        });
    }

    save_filters() {
        browser.sessionStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify({
            date_from: this.state.date_from,
            date_to: this.state.date_to,
            active_tab: this.state.active_tab,
        }));
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
            
            this.state.pos_top_donors = data.pos_top_donors;
            this.state.box_top_donors = data.box_top_donors;
            this.state.home_top_donors = data.home_top_donors;
            this.state.import_top_donors = data.import_top_donors;
            this.state.online_top_donors = data.online_top_donors;
            this.state.in_kind_top_donors = data.in_kind_top_donors;

            this.state.welfare_top_donees = data.welfare_top_donees;
            this.state.microfinance_top_donees = data.microfinance_top_donees;
            this.state.medical_top_donees = data.medical_top_donees;
        } catch (error) {
            console.error("Dashboard Fetch Error:", error);
            this.env.services.notification.add("Failed to load dashboard data.", { type: "danger" });
        }
        if (this.is_mounted) this.render_charts();
    }

    async applyFilter() {
        this.save_filters();
        await this.fetch_data();
    }

    setTab(tab) {
        this.state.active_tab = tab;
        this.save_filters();
    }

    clearFilter() {
        this.state.date_from = '';
        this.state.date_to = '';
        browser.sessionStorage.removeItem(FILTER_STORAGE_KEY);
        this.applyFilter();
    }

    setQuickDate(type) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const month = today.getMonth();
        const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

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
                data: { labels: this.state.chart_regs.labels, datasets: [{ label: 'Registrations', data: this.state.chart_regs.data, backgroundColor: "rgba(75, 192, 192, 0.8)" }] },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
        const ctx2 = $("#pm_chart_cats");
        if (ctx2.length) {
            if (this._charts.cats) this._charts.cats.destroy();
            this._charts.cats = new Chart(ctx2, {
                type: 'doughnut',
                data: { labels: this.state.chart_cats.labels, datasets: [{ data: this.state.chart_cats.data, backgroundColor: ["#4bc0c0", "#36a2eb", "#ff6384", "#ffce56", "#cc65fe", "#ff9f40"] }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }
            });
        }
    }

    formatStateName(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ') : ''; }
    getStateColor(s) {
        if (!s) return 'bg-secondary';
        s = s.toLowerCase();
        if (['register', 'available', 'paid', 'done'].includes(s)) return 'bg-success';
        if (['draft', 'pending'].includes(s)) return 'bg-warning text-dark';
        if (['reject', 'rejected', 'cancel'].includes(s)) return 'bg-danger';
        return 'bg-info text-white';
    }
    openView(model, domain = []) {
        this.actionService.doAction({ type: 'ir.actions.act_window', res_model: model, views: [[false, 'list'], [false, 'form']], domain: domain, target: 'current' });
    }
}

ProfileManagementDashboard.template = 'ProfileManagementDashboard';
registry.category("actions").add("profile_management_dashboard", ProfileManagementDashboard);