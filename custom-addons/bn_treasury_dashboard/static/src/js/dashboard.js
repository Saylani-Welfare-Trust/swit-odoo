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
            cheques:   { count: 0, total_amount: 0, states: {}, state_amounts: {} },
            deposits:  { count: 0, total_amount: 0, states: {}, state_amounts: {} },
            transfers: { count: 0, total_amount: 0, states: {}, state_amounts: {} },
        });

        onWillStart(async () => { await this.fetchData(); });
    }

    async fetchData() {
        const data = await this.env.services.rpc("/treasury/dashboard/data", {
            date_from: this.state.date_from,
            date_to: this.state.date_to,
        });
        this.state.currency  = data.currency;
        this.state.cheques   = { ...this.state.cheques,   ...data.cheques };
        this.state.deposits  = { ...this.state.deposits,  ...data.deposits };
        this.state.transfers = { ...this.state.transfers, ...data.transfers };
    }

    // NEW helper (optional but clean)
    getStateAmount(category, stateName) {
        const amounts = this.state[category].state_amounts || {};
        return amounts[stateName] || 0;
    }

    async applyFilter() {
        await this.fetchData();
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

    formatStateName(stateName) {
        if (!stateName) return '';
        return stateName.charAt(0).toUpperCase() + stateName.slice(1).replace(/_/g, ' ');
    }

    // 🟢 UPDATED: Colors now match Odoo standard exactly
    getStateColor(stateName) {
        if (!stateName) return 'bg-secondary';
        const s = stateName.toLowerCase();
        
        // Green for successful/cleared states
        if (['clear', 'cleared', 'posted', 'paid', 'done', 'transfer', 'transferred'].includes(s)) {
            return 'bg-success';
        }
        // Orange for pending/draft states
        if (['draft', 'pending', 'to_pay', 'unpaid', 'to_validate', 'waiting'].includes(s)) {
            return 'bg-warning text-dark'; // text-dark ensures readability on orange
        }
        // Red for failed/cancelled states
        if (['bounce', 'bounced', 'cancel', 'cancelled', 'late', 'rejected'].includes(s)) {
            return 'bg-danger';
        }
        // Blue for informational states
        if (['new', 'in_progress', 'open'].includes(s)) {
            return 'bg-info text-dark';
        }
        // Default grey for anything else
        return 'bg-secondary';
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

    formatCurrency(value) {
        const symbol = this.state.currency.symbol || '$';
        const position = this.state.currency.position || 'before';
        const formatted = (value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return position === 'after' ? `${formatted} ${symbol}` : `${symbol} ${formatted}`;
    }
}

registry.category("actions").add("treasury_dashboard", TreasuryDashboard);