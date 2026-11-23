/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, onMounted, useState } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

export class ProfitLossDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        
        this.trendChartRef = useRef("trendChart");
        this.breakdownChartRef = useRef("breakdownChart");
        
        this.state = useState({
            data: null,
            loading: true,
            date_from: new Date(new Date().getFullYear(), 0, 1).toISOString().split('T')[0],
            date_to: new Date().toISOString().split('T')[0],
        });

        this.charts = {};

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.loadData();
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "profit.loss.dashboard", 
                "get_dashboard_data", 
                [this.state.date_from, this.state.date_to]
            );
            this.renderCharts(); 
        } catch (error) {
            console.error("Error loading P&L data:", error);
        } finally {
            this.state.loading = false;
        }
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
        return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount);
    }

    renderCharts() {
        if (!this.state.data) return;

        // 1. Trend Chart
        if (this.trendChartRef.el && this.charts.trend) {
            this.charts.trend.destroy();
        }
        if (this.trendChartRef.el) {
            this.charts.trend = new Chart(this.trendChartRef.el, {
                type: 'bar',
                data: {
                    labels: this.state.data.trend_labels,
                    datasets: [
                        {
                            label: 'Income',
                            data: this.state.data.trend_income,
                            backgroundColor: '#28a745',
                            borderRadius: 4,
                            yAxisID: 'y', // Uses Left Axis
                        },
                        {
                            label: 'Expense',
                            data: this.state.data.trend_expense,
                            backgroundColor: '#dc3545',
                            borderRadius: 4,
                            yAxisID: 'y1', // Uses Right Axis
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { 
                        legend: { position: 'top' },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                        label += 'Rs ' + new Intl.NumberFormat('en-US').format(context.parsed.y);
                                    }
                                    return label;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {
                                display: true,
                                text: 'Income (Rs)'
                            },
                            beginAtZero: true
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            title: {
                                display: true,
                                text: 'Expense (Rs)'
                            },
                            beginAtZero: true,
                            min: 0, // <-- ADD THIS LINE
                            grid: {
                                drawOnChartArea: false, 
                            },
                        }
                    }
                }
            });
        }

        // 2. Breakdown Chart (Doughnut) - No changes needed here
        if (this.breakdownChartRef.el && this.charts.breakdown) {
            this.charts.breakdown.destroy();
        }
        if (this.breakdownChartRef.el) {
            const labels = this.state.data.expense_breakdown.map(e => e.name);
            const amounts = this.state.data.expense_breakdown.map(e => e.amount);
            const colors = ['#dc3545', '#fd7e14', '#ffc107', '#17a2b8', '#6c757d'];

            this.charts.breakdown = new Chart(this.breakdownChartRef.el, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: amounts,
                        backgroundColor: colors.slice(0, labels.length),
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'right' } },
                    cutout: '70%'
                }
            });
        }
    }
}

ProfitLossDashboard.template = "profit_loss_dashboard.ProfitLossTemplate";
registry.category("actions").add("profit_loss_dashboard", ProfitLossDashboard);