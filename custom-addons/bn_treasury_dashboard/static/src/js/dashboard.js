/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";

export class TreasuryDashboard extends Component {
    static template = "treasury_dashboard.Dashboard";

    setup() {
        this.actionService = useService("action");
        
        this.state = useState({
            date_from: '',
            date_to: '',
            currency: { symbol: '$', position: 'before' },
            cheques: { count: 0, total_amount: 0, states: {}, trend: {labels: [], data: []} },
            deposits: { count: 0, total_amount: 0, states: {}, trend: {labels: [], data: []} },
            transfers: { count: 0, total_amount: 0, states: {}, trend: {labels: [], data: []} },
        });

        this.mainChartRef = useRef("mainChart");
        this.chartInstance = null;

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
        });

        onMounted(() => {
            this.renderChart();
        });

        onWillUnmount(() => {
            this.destroyChart();
        });
    }

    async fetchData() {
        const data = await this.env.services.rpc("/treasury/dashboard/data", {
            date_from: this.state.date_from,
            date_to: this.state.date_to
        });
        this.state.currency = data.currency;
        this.state.cheques = data.cheques;
        this.state.deposits = data.deposits;
        this.state.transfers = data.transfers;
    }

    async applyFilter() {
        this.destroyChart();
        await this.fetchData();
        // Small delay to allow OWL to update the DOM before drawing the chart
        setTimeout(() => this.renderChart(), 50);
    }

    clearFilter() {
        this.state.date_from = '';
        this.state.date_to = '';
        this.applyFilter();
    }

    formatLocalDate(d) {
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    }

    setQuickFilter(type) {
        const today = new Date();
        const year = today.getFullYear();
        const month = today.getMonth();

        if (type === 'this_month') {
            this.state.date_from = this.formatLocalDate(new Date(year, month, 1));
            this.state.date_to = this.formatLocalDate(new Date(year, month + 1, 0));
        } else if (type === 'last_month') {
            this.state.date_from = this.formatLocalDate(new Date(year, month - 1, 1));
            this.state.date_to = this.formatLocalDate(new Date(year, month, 0));
        } else if (type === 'this_year') {
            this.state.date_from = this.formatLocalDate(new Date(year, 0, 1));
            this.state.date_to = this.formatLocalDate(new Date(year, 11, 31));
        }
        
        this.applyFilter();
    }

    createCustomModel(modelName) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: modelName,
            views: [[false, 'form']],
            target: 'current'
        });
    }

    openCustomModel(modelName) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: modelName,
            views: [[false, 'list'], [false, 'form']],
            target: 'current'
        });
    }

    renderChart() {
        if (!this.mainChartRef.el) return;
        
        // Use labels from Cheques (assuming all three share the same date range labels)
        const labels = this.state.cheques.trend.labels;

        const ctx = this.mainChartRef.el.getContext('2d');
        this.chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Cheques',
                        data: this.state.cheques.trend.data,
                        borderColor: '#17a2b8',
                        backgroundColor: 'rgba(23, 162, 184, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: 'Deposits',
                        data: this.state.deposits.trend.data,
                        borderColor: '#ffc107',
                        backgroundColor: 'rgba(255, 193, 7, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: 'Transfers',
                        data: this.state.transfers.trend.data,
                        borderColor: '#28a745',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: { position: 'top' },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.dataset.label}: ${this.formatCurrency(context.parsed.y)}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => this.formatCurrency(value)
                        }
                    }
                }
            }
        });
    }

    destroyChart() {
        if (this.chartInstance) {
            this.chartInstance.destroy();
            this.chartInstance = null;
        }
    }

    formatCurrency(value) {
        const symbol = this.state.currency.symbol || '$';
        const position = this.state.currency.position || 'before';
        const formatted = (value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return position === 'after' ? `${formatted} ${symbol}` : `${symbol} ${formatted}`;
    }
}

registry.category("actions").add("treasury_dashboard", TreasuryDashboard);