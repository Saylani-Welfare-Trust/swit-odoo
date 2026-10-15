/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks"; // <-- Import useService

export class TreasuryDashboard extends Component {
    static template = "treasury_dashboard.Dashboard";

    setup() {
        // 🟢 Initialize the Action Service
        this.actionService = useService("action");

        this.state = useState({
            kpis: { total_cash: 0, total_receivables: 0, total_payables: 0 },
            chart: { labels: [], receivables: [], payables: [] },
        });
        
        this.chartRef = useRef("treasuryChart");
        this.chartInstance = null;

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            
            const data = await this.env.services.rpc("/treasury/dashboard/data", {});
            this.state.kpis = data.kpis;
            this.state.chart = data.chart;
        });

        onMounted(() => {
            this.renderChart();
        });

        onWillUnmount(() => {
            if (this.chartInstance) {
                this.chartInstance.destroy();
            }
        });
    }

    // 🟢 Add the openAction method to handle menu clicks
    openAction(actionXmlId) {
        this.actionService.doAction(actionXmlId);
    }

    renderChart() {
        if (!this.chartRef.el) return;

        const ctx = this.chartRef.el.getContext('2d');
        this.chartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: this.state.chart.labels,
                datasets: [
                    {
                        label: 'Receivables',
                        data: this.state.chart.receivables,
                        backgroundColor: 'rgba(54, 162, 235, 0.6)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Payables',
                        data: this.state.chart.payables,
                        backgroundColor: 'rgba(255, 99, 132, 0.6)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
    }
}

registry.category("actions").add("treasury_dashboard", TreasuryDashboard);