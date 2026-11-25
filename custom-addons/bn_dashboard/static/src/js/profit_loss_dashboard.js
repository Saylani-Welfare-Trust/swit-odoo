/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, useState, useEffect } from "@odoo/owl";
import { loadJS, loadBundle } from "@web/core/assets";

export class ProfitLossDashboard extends Component {
    setup() {
        this.orm = useService("orm");

        this.trendChartRef = useRef("trendChart");
        this.breakdownChartRef = useRef("breakdownChart");

        const today = new Date();
        const yearStart = new Date(today.getFullYear(), 0, 1);

        this.state = useState({
            data: null,
            loading: true,
            date_from: this._toISODate(yearStart),
            date_to: this._toISODate(today),
            active_preset: "ytd",
            chart_mode: "bars", // bars | lines | mixed
        });

        this.charts = {};

        onWillStart(async () => {
            await this.loadChartJs();
            await this.loadData();
        });

        // Re-render the charts AFTER every DOM patch (mount + filter/state changes).
        useEffect(() => {
            if (this.state.loading || !this.state.data) {
                this.destroyCharts();
                return;
            }
            this.renderCharts();
            return () => this.destroyCharts();
        });
    }

    /* ------------------------------------------------------------------ */
    /* Helpers                                                             */
    /* ------------------------------------------------------------------ */

    _toISODate(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${y}-${m}-${day}`;
    }

    async loadChartJs() {
        // Odoo 17+ ships Chart.js 4.x inside `web.chartjs_lib`.
        try {
            await loadBundle("web.chartjs_lib");
        } catch (e) {
            await loadJS("/web/static/lib/Chart/Chart.js");
        }
    }

    /* ------------------------------------------------------------------ */
    /* Data loading                                                        */
    /* ------------------------------------------------------------------ */

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "profit.loss.dashboard",
                "get_dashboard_data",
                [this.state.date_from, this.state.date_to]
            );
            this.state.data = this.normalizeData(data);
        } catch (error) {
            console.error("Error loading P&L data:", error);
            this.state.data = null;
        } finally {
            this.state.loading = false;
        }
    }

    normalizeData(raw) {
        if (!raw) return null;

        const toNum = (v) => {
            if (v === null || v === undefined) return 0;
            if (typeof v === "object" && v !== null) v = v.amount ?? v.value ?? 0;
            if (typeof v === "string") v = v.replace(/,/g, "").trim();
            const n = Number(v);
            return isNaN(n) ? 0 : n;
        };

        const labels = Array.isArray(raw.trend_labels) ? raw.trend_labels.slice() : [];
        const income = (raw.trend_income || []).map(toNum);
        const expense = (raw.trend_expense || []).map((v) => Math.abs(toNum(v)));

        while (income.length < labels.length) income.push(0);
        while (expense.length < labels.length) expense.push(0);
        income.length = labels.length;
        expense.length = labels.length;

        const breakdown = (raw.expense_breakdown || []).map((e) => ({
            name: e.name ?? e.label ?? "Unknown",
            amount: Math.abs(toNum(e.amount ?? e.value)),
        }));

        return {
            total_income: toNum(raw.total_income),
            total_expense: toNum(raw.total_expense),
            net_profit: toNum(raw.net_profit),
            trend_labels: labels,
            trend_income: income,
            trend_expense: expense,
            expense_breakdown: breakdown,
        };
    }

    /* ------------------------------------------------------------------ */
    /* Filters / actions                                                   */
    /* ------------------------------------------------------------------ */

    async applyFilter(ev) {
        if (ev.target.name === "date_from") this.state.date_from = ev.target.value;
        else if (ev.target.name === "date_to") this.state.date_to = ev.target.value;
        this.state.active_preset = null;
        await this.loadData();
    }

    async applyPreset(ev) {
        const preset = ev.currentTarget.dataset.preset;
        const today = new Date();
        let from, to;

        switch (preset) {
            case "this_month":
                from = new Date(today.getFullYear(), today.getMonth(), 1);
                to = today;
                break;
            case "last_month":
                from = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                to = new Date(today.getFullYear(), today.getMonth(), 0);
                break;
            case "this_quarter": {
                const q = Math.floor(today.getMonth() / 3);
                from = new Date(today.getFullYear(), q * 3, 1);
                to = today;
                break;
            }
            case "ytd":
                from = new Date(today.getFullYear(), 0, 1);
                to = today;
                break;
            case "last_year":
                from = new Date(today.getFullYear() - 1, 0, 1);
                to = new Date(today.getFullYear() - 1, 11, 31);
                break;
            default:
                return;
        }

        this.state.date_from = this._toISODate(from);
        this.state.date_to = this._toISODate(to);
        this.state.active_preset = preset;
        await this.loadData();
    }

    setChartMode(ev) {
        this.state.chart_mode = ev.currentTarget.dataset.mode;
        // useEffect re-runs because state.chart_mode is read inside renderCharts
    }

    refresh() {
        this.loadData();
    }

    print() {
        window.print();
    }

    /* ------------------------------------------------------------------ */
    /* Formatters                                                          */
    /* ------------------------------------------------------------------ */

    formatCurrency(amount) {
        if (amount === undefined || amount === null) return "0.00";
        return new Intl.NumberFormat("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(amount);
    }

    formatPct(amount) {
        const total = this.state.data?.total_expense || 0;
        if (!total) return "0.0";
        return ((amount / total) * 100).toFixed(1);
    }

    formatMargin() {
        const d = this.state.data;
        if (!d || !d.total_income) return "0.0";
        return ((d.net_profit / d.total_income) * 100).toFixed(1);
    }

    get marginHealth() {
        const d = this.state.data;
        if (!d || !d.total_income) return { label: "—", cls: "text-bg-secondary" };
        const m = (d.net_profit / d.total_income) * 100;
        if (m < 0) return { label: "Loss", cls: "text-bg-danger" };
        if (m < 20) return { label: "Watch", cls: "text-bg-warning" };
        return { label: "Healthy", cls: "text-bg-success" };
    }

    /* ------------------------------------------------------------------ */
    /* Charts                                                              */
    /* ------------------------------------------------------------------ */

    destroyCharts() {
        Object.values(this.charts).forEach((chart) => {
            try {
                chart && chart.destroy();
            } catch (e) {
                /* ignore */
            }
        });
        this.charts = {};
    }

    buildTrendDatasets() {
        const mode = this.state.chart_mode;
        const income = this.state.data.trend_income;
        const expense = this.state.data.trend_expense;

        const incomeBar = {
            type: "bar",
            label: "Income",
            data: income,
            backgroundColor: "#28a745",
            borderColor: "#1e7e34",
            borderWidth: 1,
            borderRadius: 4,
        };
        const expenseBar = {
            type: "bar",
            label: "Expense",
            data: expense,
            backgroundColor: "#dc3545",
            borderColor: "#a71d2a",
            borderWidth: 1,
            borderRadius: 4,
        };
        const incomeLine = {
            type: "line",
            label: "Income",
            data: income,
            borderColor: "#28a745",
            backgroundColor: "rgba(40,167,69,0.15)",
            borderWidth: 3,
            tension: 0.3,
            pointRadius: 4,
            fill: false,
        };
        const expenseLine = {
            type: "line",
            label: "Expense",
            data: expense,
            borderColor: "#dc3545",
            backgroundColor: "rgba(220,53,69,0.15)",
            borderWidth: 3,
            tension: 0.3,
            pointRadius: 4,
            fill: false,
        };

        if (mode === "lines") return [incomeLine, expenseLine];
        if (mode === "mixed") return [incomeBar, expenseLine];
        return [incomeBar, expenseBar]; // "bars" (default)
    }

    renderCharts() {
        if (!this.state.data) return;
        this.destroyCharts();

        // 1. Trend chart
        if (this.trendChartRef.el) {
            this.charts.trend = new Chart(this.trendChartRef.el, {
                type: "bar",
                data: {
                    labels: this.state.data.trend_labels,
                    datasets: this.buildTrendDatasets(),
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: {
                        legend: { position: "top" },
                        tooltip: {
                            callbacks: {
                                label: (context) => {
                                    let label = context.dataset.label || "";
                                    if (label) label += ": ";
                                    if (context.parsed.y !== null && context.parsed.y !== undefined) {
                                        label +=
                                            "Rs " +
                                            new Intl.NumberFormat("en-US", {
                                                minimumFractionDigits: 2,
                                                maximumFractionDigits: 2,
                                            }).format(context.parsed.y);
                                    }
                                    return label;
                                },
                            },
                        },
                    },
                    scales: {
                        x: { grid: { display: false } },
                        y: {
                            type: "linear",
                            display: true,
                            position: "left",
                            beginAtZero: true,
                            title: { display: true, text: "Amount (Rs)" },
                        },
                    },
                },
            });
        }

        // 2. Expense breakdown doughnut
        if (this.breakdownChartRef.el) {
            const labels = this.state.data.expense_breakdown.map((e) => e.name);
            const amounts = this.state.data.expense_breakdown.map((e) => e.amount);
            const colors = ["#dc3545", "#fd7e14", "#ffc107", "#17a2b8", "#6c757d", "#6610f2", "#20c997"];

            this.charts.breakdown = new Chart(this.breakdownChartRef.el, {
                type: "doughnut",
                data: {
                    labels,
                    datasets: [
                        {
                            data: amounts,
                            backgroundColor: colors.slice(0, labels.length),
                            borderWidth: 1,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "right" },
                        tooltip: {
                            callbacks: {
                                label: (context) => {
                                    let label = context.label || "";
                                    if (label) label += ": ";
                                    if (context.parsed !== null && context.parsed !== undefined) {
                                        label +=
                                            "Rs " +
                                            new Intl.NumberFormat("en-US", {
                                                minimumFractionDigits: 2,
                                                maximumFractionDigits: 2,
                                            }).format(context.parsed);
                                    }
                                    return label;
                                },
                            },
                        },
                    },
                    cutout: "70%",
                },
            });
        }
    }
}

ProfitLossDashboard.template = "profit_loss_dashboard.ProfitLossTemplate";
registry.category("actions").add("profit_loss_dashboard", ProfitLossDashboard);