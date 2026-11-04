/** @odoo-module **/
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { Component, onWillStart, onMounted, useState, onWillDestroy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const FILTER_STORAGE_KEY = 'din_dashboard_filter_state';

export class DonationDashboard extends Component {
    setup() {
        super.setup(...arguments);
        this.orm = useService('orm');
        this.actionService = useService("action");

        this.is_mounted = false;

        this.state = useState({
            segment_l1: null, segment_l2: null, segment_l3: null, segment_l4: null,
            state_filter: '',
            amount_min: null, amount_max: null,
            date_from: '', date_to: '',

            segments_l1: [], segments_l2: [], segments_l3: [], segments_l4: [],

            kpi: { total_records: 0, total_quantity: '0', total_value: '0',
                   unique_donors: 0, state_counts: {}, state_labels: {},
                   currency_symbol: '' },
            chart_monthly: { labels: [], counts: [], values: [] },
            chart_states: { labels: [], data: [] },
            top_donors: [], top_products: [], top_categories: [], recent: [],

            category_time_series: { columns: [], rows: [], col_totals: {}, grand_total: '' },

            comparison_mode: 'month',
            comparison_period1: '',
            comparison_period2: '',
            comparison_result: { p1: {}, p2: {}, diffs: {} },
        });

        const savedStateStr = sessionStorage.getItem(FILTER_STORAGE_KEY);
        if (savedStateStr) {
            try {
                const saved = JSON.parse(savedStateStr);
                for (const key in saved) {
                    if (this.state[key] !== undefined) {
                        this.state[key] = saved[key];
                    }
                }
            } catch (e) { console.warn(e); }
        }

        this._charts = {};

        onWillStart(async () => {
            await this.fetch_dropdowns();
            this._init_comparison_periods();
            await this.fetch_data();
            await this.fetch_comparison();
        });

        onMounted(async () => {
            this.is_mounted = true;
            await this.render_all_charts();
        });

        onWillDestroy(() => {
            sessionStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify({
                segment_l1: this.state.segment_l1,
                segment_l2: this.state.segment_l2,
                segment_l3: this.state.segment_l3,
                segment_l4: this.state.segment_l4,
                state_filter: this.state.state_filter,
                amount_min: this.state.amount_min,
                amount_max: this.state.amount_max,
                date_from: this.state.date_from,
                date_to: this.state.date_to,
                comparison_mode: this.state.comparison_mode,
                comparison_period1: this.state.comparison_period1,
                comparison_period2: this.state.comparison_period2,
            }));
        });
    }

    async fetch_dropdowns() {
        const h = await this.orm.call('donation.in.kind', 'get_din_hierarchy', []);
        this.state.segments_l1 = h.segments_l1 || [];
        this.state.segments_l2 = h.segments_l2 || [];
        this.state.segments_l3 = h.segments_l3 || [];
        this.state.segments_l4 = h.segments_l4 || [];
    }

    get filteredSegmentsL2() {
        if (!this.state.segment_l1) return [];
        const pId = parseInt(this.state.segment_l1, 10);
        return this.state.segments_l2.filter(s => s.parent_id === pId);
    }
    get filteredSegmentsL3() {
        if (!this.state.segment_l2) return [];
        const pId = parseInt(this.state.segment_l2, 10);
        return this.state.segments_l3.filter(s => s.parent_id === pId);
    }
    get filteredSegmentsL4() {
        if (!this.state.segment_l3) return [];
        const pId = parseInt(this.state.segment_l3, 10);
        return this.state.segments_l4.filter(s => s.parent_id === pId);
    }

    _args() {
        let effective_segment_id = null;
        if (this.state.segment_l4) effective_segment_id = parseInt(this.state.segment_l4, 10);
        else if (this.state.segment_l3) effective_segment_id = parseInt(this.state.segment_l3, 10);
        else if (this.state.segment_l2) effective_segment_id = parseInt(this.state.segment_l2, 10);
        else if (this.state.segment_l1) effective_segment_id = parseInt(this.state.segment_l1, 10);

        return [
            this.state.date_from || null,
            this.state.date_to || null,
            effective_segment_id,
            this.state.state_filter || null,
            this.state.amount_min ? parseFloat(this.state.amount_min) : null,
            this.state.amount_max ? parseFloat(this.state.amount_max) : null,
        ];
    }

    async fetch_data() {
        const args = this._args();
        const data = await this.orm.call('donation.in.kind', 'get_din_dashboard_data', args);
        this.state.kpi = data.kpi;
        this.state.chart_monthly = data.chart_monthly;
        this.state.chart_states = data.chart_states;
        this.state.top_donors = data.top_donors;
        this.state.top_products = data.top_products;
        this.state.top_categories = data.top_categories;
        this.state.recent = data.recent;

        this.state.category_time_series =
            await this.orm.call('donation.in.kind', 'get_din_category_time_series', args);
    }

    async refresh() {
        await this.fetch_data();
        await this.fetch_comparison();
        if (this.is_mounted) await this.render_all_charts();
    }

    async onchange_segment_l1() {
        this.state.segment_l2 = null;
        this.state.segment_l3 = null;
        this.state.segment_l4 = null;
        await this.refresh();
    }
    async onchange_segment_l2() {
        this.state.segment_l3 = null;
        this.state.segment_l4 = null;
        await this.refresh();
    }
    async onchange_segment_l3() {
        this.state.segment_l4 = null;
        await this.refresh();
    }
    async onchange_filter() {
        await this.refresh();
    }

    async clear_filter() {
        this.state.segment_l1 = null;
        this.state.segment_l2 = null;
        this.state.segment_l3 = null;
        this.state.segment_l4 = null;
        this.state.state_filter = '';
        this.state.amount_min = null;
        this.state.amount_max = null;
        this.state.date_from = '';
        this.state.date_to = '';
        sessionStorage.removeItem(FILTER_STORAGE_KEY);
        await this.refresh();
    }

    async set_quick_date(type) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const m = today.getMonth();
        const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        if (type === 'this_month') {
            this.state.date_from = fmt(new Date(yyyy, m, 1));
            this.state.date_to = fmt(new Date(yyyy, m + 1, 0));
        } else if (type === 'last_month') {
            this.state.date_from = fmt(new Date(yyyy, m - 1, 1));
            this.state.date_to = fmt(new Date(yyyy, m, 0));
        } else if (type === 'this_year') {
            this.state.date_from = `${yyyy}-01-01`;
            this.state.date_to = `${yyyy}-12-31`;
        } else if (type === 'today') {
            const d = fmt(today);
            this.state.date_from = d;
            this.state.date_to = d;
        }
        await this.refresh();
    }

    async render_all_charts() {
        const ctx1 = $("#din_chart_monthly");
        if (ctx1.length) {
            if (this._charts.monthly) this._charts.monthly.destroy();
            this._charts.monthly = new Chart(ctx1, {
                type: 'bar',
                data: {
                    labels: this.state.chart_monthly.labels,
                    datasets: [{
                        label: 'Donations',
                        data: this.state.chart_monthly.counts,
                        backgroundColor: "rgba(75, 192, 192, 0.85)",
                        minBarLength: 4,
                    }],
                },
                options: { responsive: true, maintainAspectRatio: false },
            });
        }
        const ctx2 = $("#din_chart_states");
        if (ctx2.length) {
            if (this._charts.states) this._charts.states.destroy();
            this._charts.states = new Chart(ctx2, {
                type: 'doughnut',
                data: {
                    labels: this.state.chart_states.labels,
                    datasets: [{
                        data: this.state.chart_states.data,
                        backgroundColor: [
                            "#36a2eb", "#4bc0c0", "#ffce56",
                            "#ff6384", "#cc65fe", "#9966ff", "#ff9f40", "#8b6bd9",
                        ],
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { font: { size: 10 } } } },
                },
            });
        }
        const ctx3 = $("#din_chart_top_donors");
        if (ctx3.length) {
            if (this._charts.top_donors) this._charts.top_donors.destroy();
            this._charts.top_donors = new Chart(ctx3, {
                type: 'bar',
                data: {
                    labels: this.state.top_donors.map(d => d.name && d.name.length > 20 ? d.name.substring(0, 20) + '…' : d.name),
                    datasets: [{
                        label: 'Value',
                        data: this.state.top_donors.map(d => d.value),
                        backgroundColor: "rgba(153, 102, 255, 0.85)",
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false, indexAxis: 'y',
                    plugins: { legend: { display: false } },
                },
            });
        }
        const ctx4 = $("#din_chart_top_products");
        if (ctx4.length) {
            if (this._charts.top_products) this._charts.top_products.destroy();
            this._charts.top_products = new Chart(ctx4, {
                type: 'bar',
                data: {
                    labels: this.state.top_products.map(p => p.name && p.name.length > 25 ? p.name.substring(0, 25) + '…' : p.name),
                    datasets: [{
                        label: 'Value',
                        data: this.state.top_products.map(p => p.value),
                        backgroundColor: "rgba(255, 159, 64, 0.85)",
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false, indexAxis: 'y',
                    plugins: { legend: { display: false } },
                },
            });
        }
    }

    _init_comparison_periods() {
        const today = new Date();
        const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
        if (this.state.comparison_mode === 'year') {
            if (!this.state.comparison_period1) this.state.comparison_period1 = String(today.getFullYear() - 1);
            if (!this.state.comparison_period2) this.state.comparison_period2 = String(today.getFullYear());
        } else {
            if (!this.state.comparison_period1) this.state.comparison_period1 = fmt(new Date(today.getFullYear(), today.getMonth() - 1, 1));
            if (!this.state.comparison_period2) this.state.comparison_period2 = fmt(today);
        }
    }

    async onchange_comparison_mode() {
        this.state.comparison_period1 = '';
        this.state.comparison_period2 = '';
        this._init_comparison_periods();
        await this.fetch_comparison();
    }

    async fetch_comparison() {
        let effective_segment_id = null;
        if (this.state.segment_l4) effective_segment_id = parseInt(this.state.segment_l4, 10);
        else if (this.state.segment_l3) effective_segment_id = parseInt(this.state.segment_l3, 10);
        else if (this.state.segment_l2) effective_segment_id = parseInt(this.state.segment_l2, 10);
        else if (this.state.segment_l1) effective_segment_id = parseInt(this.state.segment_l1, 10);

        const args = [
            this.state.comparison_mode,
            this.state.comparison_period1,
            this.state.comparison_period2,
            effective_segment_id,
            this.state.state_filter || null,
            this.state.amount_min ? parseFloat(this.state.amount_min) : null,
            this.state.amount_max ? parseFloat(this.state.amount_max) : null,
        ];
        this.state.comparison_result = await this.orm.call('donation.in.kind', 'get_din_comparison', args);
    }

    open_donation(id) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'donation.in.kind',
            res_id: id,
            view_mode: 'form',
            target: 'current',
        });
    }

    open_donation_list(state_filter = null) {
        const domain = [];
        if (this.state.date_from) domain.push(['create_date', '>=', this.state.date_from + ' 00:00:00']);
        if (this.state.date_to) domain.push(['create_date', '<=', this.state.date_to + ' 23:59:59']);

        let effective_segment_id = null;
        if (this.state.segment_l4) effective_segment_id = parseInt(this.state.segment_l4, 10);
        else if (this.state.segment_l3) effective_segment_id = parseInt(this.state.segment_l3, 10);
        else if (this.state.segment_l2) effective_segment_id = parseInt(this.state.segment_l2, 10);
        else if (this.state.segment_l1) effective_segment_id = parseInt(this.state.segment_l1, 10);

        if (effective_segment_id) domain.push(['analytical_account_id', 'child_of', effective_segment_id]);
        if (state_filter) domain.push(['state', '=', state_filter]);

        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'donation.in.kind',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
        });
    }
}

DonationDashboard.template = 'DonationDashboard';
registry.category("actions").add("donation_dashboard", DonationDashboard);