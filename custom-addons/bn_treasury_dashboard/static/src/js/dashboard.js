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
            cheques: { count: 0, total_amount: 0, states: {}, trend_data: [] },
            deposits: { count: 0, total_amount: 0, states: {}, trend_data: [] },
            transfers: { count: 0, total_amount: 0, states: {}, trend_data: [] },
        });

        this.chequeChartRef = useRef("chequeChart");
        this.depositChartRef = useRef("depositChart");
        this.transferChartRef = useRef("transferChart");
        this.charts = [];

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
        });

        onMounted(() => {
            this.renderCharts();
        });

        onWillUnmount(() => {
            this.destroyCharts();
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
        this.destroyCharts();
        await this.fetchData();
        // Wait a tiny bit for OWL to update the DOM before drawing new charts
        setTimeout(() => this.renderCharts(), 50); 
    }

    clearFilter() {
        this.state.date_from = '';
        this.state.date_to = '';
        this.applyFilter();
    }

    // Helper to format local dates safely without timezone shifts
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

    renderCharts() {
        this.destroyCharts();
        this.renderSparkline(this.chequeChartRef, this.state.cheques.trend_data, '#17a2b8');
        this.renderSparkline(this.depositChartRef, this.state.deposits.trend_data, '#ffc107');
        this.renderSparkline(this.transferChartRef, this.state.transfers.trend_data, '#28a745');
    }

    destroyCharts() {
        this.charts.forEach(chart => chart.destroy());
        this.charts = [];
    }

    renderSparkline(ref, data, color) {
        if (!ref.el || !data || data.length === 0) return;
        
        const ctx = ref.el.getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: new Array(data.length).fill(''),
                datasets: [{
                    data: data,
                    borderColor: color,
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: { x: { display: false }, y: { display: false, beginAtZero: true } }
            }
        });
        this.charts.push(chart);
    }

    openCustomModel(modelName) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: modelName,
            views: [[false, 'list'], [false, 'form']],
            target: 'current'
        });
    }

    formatCurrency(value) {
        const symbol = this.state.currency.symbol || '$';
        const position = this.state.currency.position || 'before';
        const formatted = (value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return position === 'after' ? `${formatted} ${symbol}` : `${symbol} ${formatted}`;
    }
}

registry.category("actions").add("treasury_dashboard", TreasuryDashboard);