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
            currency: { symbol: '$', position: 'before' },
            cheques: { count: 0, total_amount: 0, states: {}, trend_data: [] },
            deposits: { count: 0, total_amount: 0, states: {}, trend_data: [] },
            transfers: { count: 0, total_amount: 0, states: {}, trend_data: [] },
        });

        // References for the mini charts
        this.chequeChartRef = useRef("chequeChart");
        this.depositChartRef = useRef("depositChart");
        this.transferChartRef = useRef("transferChart");
        this.charts = [];

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            const data = await this.env.services.rpc("/treasury/dashboard/data", {});
            this.state.currency = data.currency;
            this.state.cheques = data.cheques;
            this.state.deposits = data.deposits;
            this.state.transfers = data.transfers;
        });

        onMounted(() => {
            // Render mini line charts
            this.renderSparkline(this.chequeChartRef, this.state.cheques.trend_data, '#17a2b8'); // Info color
            this.renderSparkline(this.depositChartRef, this.state.deposits.trend_data, '#ffc107'); // Warning color
            this.renderSparkline(this.transferChartRef, this.state.transfers.trend_data, '#28a745'); // Success color
        });

        onWillUnmount(() => {
            this.charts.forEach(chart => chart.destroy());
        });
    }

    renderSparkline(ref, data, color) {
        if (!ref.el || !data || data.length === 0) return;
        
        const ctx = ref.el.getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: new Array(data.length).fill(''), // Hide X axis labels
                datasets: [{
                    data: data,
                    borderColor: color,
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3, // Makes the line smooth
                    pointRadius: 0 // Hides the dots on the line
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: { 
                    x: { display: false }, 
                    y: { display: false, beginAtZero: true } 
                }
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