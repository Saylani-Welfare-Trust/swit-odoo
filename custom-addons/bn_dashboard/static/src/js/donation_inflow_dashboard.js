/** @odoo-module **/
import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";
import { browser } from "@web/core/browser/browser";
import { Component, onWillStart, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const FILTER_STORAGE_KEY = 'donation_inflow_dashboard_filters';

export class DonationInflowDashboard extends Component {
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

            // Segment filters
            segment_type: savedFilters.segment_type || '',
            segment_l1: savedFilters.segment_l1 || null,
            segment_l2: savedFilters.segment_l2 || null,
            segment_l3: savedFilters.segment_l3 || null,
            segment_l4: savedFilters.segment_l4 || null,
            segments_l1: [],
            segments_l2: [],
            segments_l3: [],
            segments_l4: [],

            comparison_mode: savedFilters.comparison_mode || 'month',
            comparison_period1: savedFilters.comparison_period1 || '',
            comparison_period2: savedFilters.comparison_period2 || '',
            comparison_result: { p1: {}, p2: {}, diffs: {} },

            kpi: { total_amount: '0', total_records: 0, unique_donors: 0, file_amount: '0', fee_amount: '0', api_amount: '0' },
            chart_source: { labels: [], data: [] },
            chart_monthly: { labels: [], data: [] },
            recent: [],
        });

        this._charts = {};
        this.is_mounted = false;

        onWillStart(async () => {
            // Chart.js of Odoo, loaded only when a dashboard opens
            await loadBundle("web.chartjs_lib");
            await this.fetch_segments();
            this._init_comparison_periods();
            await this.fetch_data();
            await this.fetch_comparison();
        });

        onMounted(() => {
            this.is_mounted = true;
            this.render_charts();
        });
    }

    // ---------- Segment hierarchy ----------
    async fetch_segments() {
        try {
            const hierarchy = await this.orm.call('donation.inflow.dashboard', 'get_segment_hierarchy', []);
            this.state.segments_l1 = hierarchy.segments_l1 || [];
            this.state.segments_l2 = hierarchy.segments_l2 || [];
            this.state.segments_l3 = hierarchy.segments_l3 || [];
            this.state.segments_l4 = hierarchy.segments_l4 || [];
        } catch (error) {
            console.error("Segment Fetch Error:", error);
        }
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

    // ---------- Filter persistence ----------
    save_filters() {
        browser.sessionStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify({
            date_from: this.state.date_from,
            date_to: this.state.date_to,
            segment_type: this.state.segment_type,
            segment_l1: this.state.segment_l1,
            segment_l2: this.state.segment_l2,
            segment_l3: this.state.segment_l3,
            segment_l4: this.state.segment_l4,
            comparison_mode: this.state.comparison_mode,
            comparison_period1: this.state.comparison_period1,
            comparison_period2: this.state.comparison_period2,
        }));
    }

    _segment_args() {
        return [
            this.state.segment_l1 ? parseInt(this.state.segment_l1, 10) : null,
            this.state.segment_l2 ? parseInt(this.state.segment_l2, 10) : null,
            this.state.segment_l3 ? parseInt(this.state.segment_l3, 10) : null,
            this.state.segment_l4 ? parseInt(this.state.segment_l4, 10) : null,
            this.state.segment_type || null,
        ];
    }

    // ---------- Data fetch ----------
    async fetch_data() {
        try {
            const data = await this.orm.call('donation.inflow.dashboard', 'get_dashboard_data', [
                this.state.date_from || null,
                this.state.date_to || null,
                ...this._segment_args(),
            ]);
            this.state.kpi = data.kpi;
            this.state.chart_source = data.chart_source;
            this.state.chart_monthly = data.chart_monthly;
            this.state.recent = data.recent;
        } catch (error) {
            console.error("Dashboard Fetch Error:", error);
            this.env.services.notification.add("Failed to load dashboard data.", { type: "danger" });
        }
        if (this.is_mounted) this.render_charts();
    }

    async fetch_comparison() {
        try {
            const data = await this.orm.call('donation.inflow.dashboard', 'get_comparison_data', [
                this.state.comparison_mode,
                this.state.comparison_period1,
                this.state.comparison_period2,
                ...this._segment_args(),
            ]);
            this.state.comparison_result = data;
        } catch (error) {
            console.error("Comparison Fetch Error:", error);
        }
    }

    // ---------- Handlers ----------
    async applyFilter() {
        this.save_filters();
        await this.fetch_data();
        await this.fetch_comparison();
    }

    clearFilter() {
        this.state.date_from = '';
        this.state.date_to = '';
        this.state.segment_type = '';
        this.state.segment_l1 = null;
        this.state.segment_l2 = null;
        this.state.segment_l3 = null;
        this.state.segment_l4 = null;
        browser.sessionStorage.removeItem(FILTER_STORAGE_KEY);
        this.applyFilter();
    }

    async onchange_segment_l1() {
        this.state.segment_l2 = null;
        this.state.segment_l3 = null;
        this.state.segment_l4 = null;
        await this.applyFilter();
    }
    async onchange_segment_l2() {
        this.state.segment_l3 = null;
        this.state.segment_l4 = null;
        await this.applyFilter();
    }
    async onchange_segment_l3() {
        this.state.segment_l4 = null;
        await this.applyFilter();
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
        } else if (type === 'today') {
            const d = fmt(today);
            this.state.date_from = d;
            this.state.date_to = d;
        }
        this.applyFilter();
    }

    // ---------- Comparison mode ----------
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

    // ---------- Charts ----------
    render_charts() {
        const ctx1 = $("#di_chart_monthly");
        if (ctx1.length) {
            if (this._charts.monthly) this._charts.monthly.destroy();
            this._charts.monthly = new Chart(ctx1, {
                type: 'bar',
                data: {
                    labels: this.state.chart_monthly.labels,
                    datasets: [{
                        label: 'Donation Amount',
                        data: this.state.chart_monthly.data,
                        backgroundColor: "rgba(75, 192, 192, 0.85)",
                        minBarLength: 4,
                    }],
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
        const ctx2 = $("#di_chart_source");
        if (ctx2.length) {
            if (this._charts.source) this._charts.source.destroy();
            this._charts.source = new Chart(ctx2, {
                type: 'doughnut',
                data: {
                    labels: this.state.chart_source.labels,
                    datasets: [{
                        data: this.state.chart_source.data,
                        backgroundColor: ["#36a2eb", "#ffce56", "#4bc0c0", "#ff6384", "#cc65fe"],
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { font: { size: 10 } } } },
                },
            });
        }
    }
}

DonationInflowDashboard.template = 'DonationInflowDashboard';
registry.category("actions").add("donation_inflow_dashboard", DonationInflowDashboard);