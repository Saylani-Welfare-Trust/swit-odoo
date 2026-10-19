/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class TreasuryDashboard extends Component {
    static template = "treasury_dashboard.Dashboard";

    setup() {
        this.actionService = useService("action");
        
        this.state = useState({
            date_from: '',
            date_to: '',
            currency: { symbol: '$', position: 'before' },
            cheques: { count: 0, total_amount: 0, states: {} },
            deposits: { count: 0, total_amount: 0, states: {} },
            transfers: { count: 0, total_amount: 0, states: {} },
        });

        onWillStart(async () => {
            await this.fetchData();
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
        await this.fetchData();
    }

    clearFilter() {
        this.state.date_from = '';
        this.state.date_to = '';
        this.applyFilter();
    }

    // Helper to format local dates safely
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