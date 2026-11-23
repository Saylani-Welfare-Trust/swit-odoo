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

        this.state = useState({
            data: null,
            loading: true,
            date_from: new Date(new Date().getFullYear(), 0, 1).toISOString().split("T")[0],
            date_to: new Date().toISOString().split("T")[0],
        });

        this.charts = {};

        onWillStart(async () => {
            await this.loadChartJs();
            await this.loadData();
        });

        // Re-render the charts AFTER every DOM patch (initial mount + each filter change).
        // The canvas elements only exist when state.loading === false && state.data !== null.
        useEffect(() => {
            if (this.state.loading || !this.state.data) {
                this.destroyCharts();
                return;
            }
            this.renderCharts();
            return () => this.destroyCharts();
        });
    }

    async loadChartJs() {
        // Odoo 17+ ships Chart.js 4.x inside the `web.chartjs_lib` bundle.
        // Odoo 16 and below use the legacy /web/static/lib/Chart/Chart.js path.
        try {
            await loadBundle("web.chartjs_lib");
        } catch (e) {
            await loadJS("/web/static/lib/Chart/Chart.js");
        }
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "profit.loss.dashboard",
                "get_dashboard_data",
                [this.state.date_from, this.state.date_to]
            );
            this.state.data = this.normalizeData(data);
            console.debug("[P&L] trend_labels :", this.state.data.trend_labels);
            console.debug("[P&L] trend_income :", this.state.data.trend_income);
            console.debug("[P&L] trend_expense:", this.state.data.trend_expense);
        } catch (error) {
            console.error("Error loading P&L data:", error);
            this.state.data = null;
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Defensive normalisation so the chart never silently breaks because of:
     *  - negative expense balances (Odoo stores expense as credit = negative)
     *  - formatted strings like "1,234.56" or dicts coming back from Python
     *  - mismatched array lengths between labels/income/expense
     */
    normalizeData(raw) {
        if (!raw) {
            return null;
        }

        const toNum = (v) => {
            if (v === null || v === undefined) return 0;
            if (typeof v === "object" && v !== null) {
                v = v.amount ?? v.value ?? 0;
            }
            if (typeof v === "string") {
                v = v.replace(/,/g, "").trim();
            }
            const n = Number(v);
            return isNaN(n) ? 0 : n;
        };

        const labels = Array.isArray(raw.trend_labels) ? raw.trend_labels.slice() : [];
        const income = (raw.trend_income || []).map(toNum);
        const expense = (raw.trend_expense || []).map((v) => Math.abs(toNum(v)));

        // Pad with zeros so all series have the same length as the labels
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

    async applyFilter(ev) {
        if (ev.target.name === "date_from") {
            this.state.date_from = ev.target.value;
        } else if (ev.target.name === "date_to") {
            this.state.date_to = ev.target.value;
        }
        await this.loadData();
    }

    formatCurrency(amount) {
        if (amount === undefined || amount === null) return "0.00";
        return new Intl.NumberFormat("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(amount);
    }

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

    renderCharts() {
        if (!this.state.data) return;

        this.destroyCharts();

        // 1. Trend chart (Income bars + Expense line on a separate y-axis)
        if (this.trendChartRef.el) {
            this.charts.trend = new Chart(this.trendChartRef.el, {
                type: "bar",
                data: {
                    labels: this.state.data.trend_labels,
                    datasets: [
                        {
                            type: "bar",
                            label: "Income",
                            data: this.state.data.trend_income,
                            backgroundColor: "#28a745",
                            borderRadius: 4,
                            yAxisID: "y",
                        },
                        {
                            type: "line",
                            label: "Expense",
                            data: this.state.data.trend_expense,
                            borderColor: "#dc3545",
                            backgroundColor: "#dc3545",
                            borderWidth: 3,
                            tension: 0.3,
                            pointRadius: 5,
                            pointHoverRadius: 7,
                            fill: false,
                            yAxisID: "y1",
                            clip: false,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: "index",
                        intersect: false,
                    },
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
                        y: {
                            type: "linear",
                            display: true,
                            position: "left",
                            beginAtZero: true,
                            title: { display: true, text: "Income (Rs)" },
                        },
                        y1: {
                            type: "linear",
                            display: true,
                            position: "right",
                            beginAtZero: true,
                            grid: { drawOnChartArea: false },
                            title: { display: true, text: "Expense (Rs)" },
                        },
                    },
                },
            });
        }

        // 2. Breakdown chart (Doughnut)
        if (this.breakdownChartRef.el) {
            const labels = this.state.data.expense_breakdown.map((e) => e.name);
            const amounts = this.state.data.expense_breakdown.map((e) => e.amount);
            const colors = ["#dc3545", "#fd7e14", "#ffc107", "#17a2b8", "#6c757d"];

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