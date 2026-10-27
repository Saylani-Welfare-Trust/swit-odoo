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
            branch_id: '',
            province_id: '',
            city_id: '',
            zone_id: '',
            segment_id: '',
            amount_min: '',
            amount_max: '',
            analytic_accounts: [],
            provinces: [],
            cities: [],
            zones: [],
            segments: [],
            currency: { symbol: '$', position: 'before' },
            cheques:   { count: 0, total_amount: 0, states: {}, state_amounts: {} },
            deposits:  { count: 0, total_amount: 0, states: {}, state_amounts: {} },
            transfers: { count: 0, total_amount: 0, states: {}, state_amounts: {} },
        });

        onWillStart(async () => { await this.fetchData(); });
    }

    get filteredCities() {
        if (!this.state.province_id) return this.state.cities;
        const pId = parseInt(this.state.province_id, 10);
        return this.state.cities.filter(c => c.province_id === pId);
    }

    get filteredZones() {
        if (!this.state.city_id) return this.state.zones;
        const cId = parseInt(this.state.city_id, 10);
        return this.state.zones.filter(z => z.city_id === cId);
    }

    get filteredBranches() {
        if (this.state.zone_id) {
            const zId = parseInt(this.state.zone_id, 10);
            return this.state.analytic_accounts.filter(b => b.zone_id === zId);
        }
        if (this.state.city_id) {
            const cId = parseInt(this.state.city_id, 10);
            return this.state.analytic_accounts.filter(b => b.city_id === cId);
        }
        if (this.state.province_id) {
            const pId = parseInt(this.state.province_id, 10);
            return this.state.analytic_accounts.filter(b => b.province_id === pId);
        }
        return this.state.analytic_accounts;
    }

    async fetchData() {
        try {
            const data = await this.env.services.rpc("/treasury/dashboard/data", {
                date_from: this.state.date_from,
                date_to: this.state.date_to,
                analytic_account_id: this.state.branch_id ? parseInt(this.state.branch_id, 10) : null,
                province_id: this.state.province_id ? parseInt(this.state.province_id, 10) : null,
                city_id: this.state.city_id ? parseInt(this.state.city_id, 10) : null,
                zone_id: this.state.zone_id ? parseInt(this.state.zone_id, 10) : null,
                segment_id: this.state.segment_id ? parseInt(this.state.segment_id, 10) : null,
                amount_min: this.state.amount_min ? parseFloat(this.state.amount_min) : null,
                amount_max: this.state.amount_max ? parseFloat(this.state.amount_max) : null,
            });
            this.state.analytic_accounts = data.analytic_accounts || [];
            this.state.provinces = data.provinces || [];
            this.state.cities = data.cities || [];
            this.state.zones = data.zones || [];
            this.state.segments = data.segments || [];
            this.state.currency  = data.currency;
            this.state.cheques   = { ...this.state.cheques,   ...data.cheques };
            this.state.deposits  = { ...this.state.deposits,  ...data.deposits };
            this.state.transfers = { ...this.state.transfers, ...data.transfers };
        } catch (error) {
            console.error("Dashboard Fetch Error:", error);
        }
    }

    async onchange_province() {
        this.state.city_id = '';
        this.state.zone_id = '';
        this.state.branch_id = '';
        await this.applyFilter();
    }

    async onchange_city() {
        this.state.zone_id = '';
        this.state.branch_id = '';
        await this.applyFilter();
    }
    
    async onchange_zone() {
        this.state.branch_id = '';
        await this.applyFilter();
    }

    async applyFilter() {
        await this.fetchData();
    }

    clearFilter() {
        this.state.date_from = '';
        this.state.date_to = '';
        this.state.branch_id = '';
        this.state.province_id = '';
        this.state.city_id = '';
        this.state.zone_id = '';
        this.state.segment_id = '';
        this.state.amount_min = '';
        this.state.amount_max = '';
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

    getStateColor(stateName) {
        if (!stateName) return 'bg-secondary text-white';
        const s = stateName.toLowerCase();
        
        if (['clear', 'cleared', 'posted', 'paid', 'done', 'transfer', 'transferred'].includes(s)) {
            return 'bg-success text-white';
        }
        if (['draft', 'pending', 'to_pay', 'unpaid', 'to_validate', 'waiting'].includes(s)) {
            return 'bg-warning text-dark'; 
        }
        if (['bounce', 'bounced', 'cancel', 'cancelled', 'late', 'rejected'].includes(s)) {
            return 'bg-danger text-white';
        }
        if (['new', 'in_progress', 'open'].includes(s)) {
            return 'bg-info text-dark';
        }
        return 'bg-secondary text-white';
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