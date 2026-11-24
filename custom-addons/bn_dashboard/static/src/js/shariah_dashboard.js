/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, useState, useEffect } from "@odoo/owl";
import { loadJS, loadBundle } from "@web/core/assets";

export class ShariahDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.trendRef = useRef("trendChart");
        this.inflowRef = useRef("inflowChart");
        this.outflowRef = useRef("outflowChart");

        const today = new Date();
        this.state = useState({
            data: null,
            loading: true,
            date_from: this._iso(new Date(today.getFullYear(), 0, 1)),
            date_to: this._iso(today),
            active_preset: "ytd",
            analytic_id: false,
            segments: [],
        });

        this.charts = {};

        onWillStart(async () => {
            await this._loadChartJs();
            await this.fetch_dropdowns();
            await this.loadData();
        });

        useEffect(() => {
            if (this.state.loading || !this.state.data) {
                this._destroyCharts();
                return;
            }
            this.renderCharts();
            return () => this._destroyCharts();
        });
    }

    _iso(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${y}-${m}-${day}`;
    }

    async _loadChartJs() {
        try {
            await loadBundle("web.chartjs_lib");
        } catch (e) {
            await loadJS("/web/static/lib/Chart/Chart.js");
        }
    }

    async fetch_dropdowns() {
        try {
            // Fetch segments (analytic accounts) - matching the 'Segment' plan
            const segments = await this.orm.searchRead(
                "account.analytic.account",
                [["plan_id.name", "=", "Segment"]],
                ["id", "name"]
            );
            this.state.segments = segments;
        } catch (err) {
            console.error("Failed to load segments:", err);
        }
    }

    async loadData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "shariah.dashboard",
                "get_dashboard_data",
                [
                    this.state.date_from || false, 
                    this.state.date_to || false, 
                    this.state.analytic_id || false
                ]
            );
        } catch (err) {
            console.error("[Shariah Dashboard] failed:", err);
            this.state.data = null;
        } finally {
            this.state.loading = false;
        }
    }

    async applyFilter(ev) {
        if (ev.target.name === "date_from") this.state.date_from = ev.target.value;
        else if (ev.target.name === "date_to") this.state.date_to = ev.target.value;
        else if (ev.target.name === "analytic_id") this.state.analytic_id = ev.target.value ? parseInt(ev.target.value, 10) : false;
        this.state.active_preset = null;
        await this.loadData();
    }

    async applyPreset(ev) {
        const preset = ev.currentTarget.dataset.preset;
        const t = new Date();
        let from, to;
        switch (preset) {
            case "this_month":
                from = new Date(t.getFullYear(), t.getMonth(), 1);
                to = t; break;
            case "last_month":
                from = new Date(t.getFullYear(), t.getMonth() - 1, 1);
                to = new Date(t.getFullYear(), t.getMonth(), 0); break;
            case "this_quarter": {
                const q = Math.floor(t.getMonth() / 3);
                from = new Date(t.getFullYear(), q * 3, 1);
                to = t; break;
            }
            case "ytd":
                from = new Date(t.getFullYear(), 0, 1);
                to = t; break;
            case "all_time":
                from = null; to = null; break;
            default:
                return;
        }
        this.state.date_from = from ? this._iso(from) : "";
        this.state.date_to = to ? this._iso(to) : "";
        this.state.active_preset = preset;
        await this.loadData();
    }

    refresh() { return this.loadData(); }
    print() { window.print(); }

    formatCurrency(v) {
        if (v === undefined || v === null) return "0.00";
        return new Intl.NumberFormat("en-US", {
            minimumFractionDigits: 2, maximumFractionDigits: 2,
        }).format(v);
    }

    _destroyCharts() {
        Object.values(this.charts).forEach((c) => { try { c && c.destroy(); } catch (e) {} });
        this.charts = {};
    }

    renderCharts() {
        this._destroyCharts();
        const d = this.state.data;
        if (!d) return;

        // Trend
        if (this.trendRef.el) {
            this.charts.trend = new Chart(this.trendRef.el, {
                type: "bar",
                data: {
                    labels: d.trend.map((t) => t.label),
                    datasets: [
                        {
                            label: "Inflows",
                            data: d.trend.map((t) => t.inflow),
                            backgroundColor: "#28a745",
                            borderRadius: 4,
                        },
                        {
                            label: "Outflows",
                            data: d.trend.map((t) => t.outflow),
                            backgroundColor: "#dc3545",
                            borderRadius: 4,
                        },
                    ],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: { legend: { position: "top" } },
                    scales: {
                        x: { grid: { display: false } },
                        y: { beginAtZero: true, title: { display: true, text: "Amount (Rs)" } },
                    },
                },
            });
        }

        // Inflow Doughnut
        if (this.inflowRef.el) {
            const items = d.inflows.filter((x) => x.amount > 0);
            this.charts.inflow = new Chart(this.inflowRef.el, {
                type: "doughnut",
                data: {
                    labels: items.map((x) => x.label),
                    datasets: [{
                        data: items.map((x) => x.amount),
                        backgroundColor: items.map((x) => x.color),
                        borderWidth: 1,
                    }],
                },
                options: { responsive: true, maintainAspectRatio: false, cutout: "70%", plugins: { legend: { position: "right" } } },
            });
        }

        // Outflow Doughnut
        if (this.outflowRef.el) {
            const items = d.outflows.filter((x) => x.amount > 0);
            this.charts.outflow = new Chart(this.outflowRef.el, {
                type: "doughnut",
                data: {
                    labels: items.map((x) => x.label),
                    datasets: [{
                        data: items.map((x) => x.amount),
                        backgroundColor: items.map((x) => x.color),
                        borderWidth: 1,
                    }],
                },
                options: { responsive: true, maintainAspectRatio: false, cutout: "70%", plugins: { legend: { position: "right" } } },
            });
        }
    }
}

ShariahDashboard.template = "bn_dashboard.ShariahDashboardTemplate";
registry.category("actions").add("shariah_dashboard", ShariahDashboard);