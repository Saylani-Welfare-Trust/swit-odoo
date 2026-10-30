/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser"; // <-- IMPORTED BROWSER
import { useService } from "@web/core/utils/hooks";

const FILTER_STORAGE_KEY = 'treasury_dashboard_filters';

export class TreasuryDashboard extends Component {
    static template = "treasury_dashboard.Dashboard";

    setup() {
        this.actionService = useService("action");

        // 1. Load saved filters from sessionStorage if they exist
        let savedFilters = {};
        const rawFilters = browser.sessionStorage.getItem(FILTER_STORAGE_KEY);
        if (rawFilters) {
            try {
                savedFilters = JSON.parse(rawFilters);
            } catch (e) {
                console.warn("Failed to parse saved filters");
            }
        }

        // 2. Initialize state with saved filters (or defaults)
        this.state = useState({
            date_from: savedFilters.date_from || '',
            date_to: savedFilters.date_to || '',
            branch_id: savedFilters.branch_id || '',
            province_id: savedFilters.province_id || '',
            city_id: savedFilters.city_id || '',
            zone_id: savedFilters.zone_id || '',
            segment_l1: savedFilters.segment_l1 || '',
            segment_l2: savedFilters.segment_l2 || '',
            segment_l3: savedFilters.segment_l3 || '',
            segment_l4: savedFilters.segment_l4 || '',
            amount_min: savedFilters.amount_min || '',
            amount_max: savedFilters.amount_max || '',
            
            analytic_accounts: [],
            provinces: [],
            cities: [],
            zones: [],
            segments_l1: [],
            segments_l2: [],
            segments_l3: [],
            segments_l4: [],
            currency: { symbol: '$', position: 'before' },
            cheques:   { count: 0, total_amount: 0, states: {}, state_amounts: {} },
            deposits:  { count: 0, total_amount: 0, states: {}, state_amounts: {} },
            transfers: { count: 0, total_amount: 0, states: {}, state_amounts: {} },
        });

        onWillStart(async () => { await this.fetchData(); });
    }

    // Helper to save current filters to sessionStorage
    save_filters() {
        const filters = {
            date_from: this.state.date_from,
            date_to: this.state.date_to,
            branch_id: this.state.branch_id,
            province_id: this.state.province_id,
            city_id: this.state.city_id,
            zone_id: this.state.zone_id,
            segment_l1: this.state.segment_l1,
            segment_l2: this.state.segment_l2,
            segment_l3: this.state.segment_l3,
            segment_l4: this.state.segment_l4,
            amount_min: this.state.amount_min,
            amount_max: this.state.amount_max,
        };
        browser.sessionStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(filters));
    }

    // Location Cascades
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

    // Segment Cascades
    get filteredSegmentsL2() {
        if (!this.state.segment_l1) return [];
        const pId = parseInt(this.state.segment_l1, 10);
        return this.state.segments_l2.filter(s => s.parent_id === pId);
    }
    get filteredSegmentsL3() {
        if (!this.state.segment_l2) return [];
        const pId = parseInt(this.state.segment_l2, 10);
        return this.state.segments_l3.filter(s => s.parent_id === pId);
    }
    get filteredSegmentsL4() {
        if (!this.state.segment_l3) return [];
        const pId = parseInt(this.state.segment_l3, 10);
        return this.state.segments_l4.filter(s => s.parent_id === pId);
    }

    async fetchData() {
        try {
            // Determine which segment level is actually selected
            let effective_segment_id = null;
            if (this.state.segment_l4) effective_segment_id = parseInt(this.state.segment_l4, 10);
            else if (this.state.segment_l3) effective_segment_id = parseInt(this.state.segment_l3, 10);
            else if (this.state.segment_l2) effective_segment_id = parseInt(this.state.segment_l2, 10);
            else if (this.state.segment_l1) effective_segment_id = parseInt(this.state.segment_l1, 10);

            const data = await this.env.services.rpc("/treasury/dashboard/data", {
                date_from: this.state.date_from,
                date_to: this.state.date_to,
                analytic_account_id: this.state.branch_id ? parseInt(this.state.branch_id, 10) : null,
                province_id: this.state.province_id ? parseInt(this.state.province_id, 10) : null,
                city_id: this.state.city_id ? parseInt(this.state.city_id, 10) : null,
                zone_id: this.state.zone_id ? parseInt(this.state.zone_id, 10) : null,
                segment_id: effective_segment_id,
                amount_min: this.state.amount_min ? parseFloat(this.state.amount_min) : null,
                amount_max: this.state.amount_max ? parseFloat(this.state.amount_max) : null,
            });
            this.state.analytic_accounts = data.analytic_accounts || [];
            this.state.provinces = data.provinces || [];
            this.state.cities = data.cities || [];
            this.state.zones = data.zones || [];
            this.state.segments_l1 = data.segments_l1 || [];
            this.state.segments_l2 = data.segments_l2 || [];
            this.state.segments_l3 = data.segments_l3 || [];
            this.state.segments_l4 = data.segments_l4 || [];
            this.state.currency  = data.currency;
            this.state.cheques   = { ...this.state.cheques,   ...data.cheques };
            this.state.deposits  = { ...this.state.deposits,  ...data.deposits };
            this.state.transfers = { ...this.state.transfers, ...data.transfers };
        } catch (error) {
            console.error("Dashboard Fetch Error:", error);
        }
    }

    // Location Handlers
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

    // Segment Handlers
    async onchange_segment_l1() {
        this.state.segment_l2 = '';
        this.state.segment_l3 = '';
        this.state.segment_l4 = '';
        await this.applyFilter();
    }
    async onchange_segment_l2() {
        this.state.segment_l3 = '';
        this.state.segment_l4 = '';
        await this.applyFilter();
    }
    async onchange_segment_l3() {
        this.state.segment_l4 = '';
        await this.applyFilter();
    }

    async applyFilter() {
        this.save_filters(); // <-- SAVE FILTERS
        await this.fetchData();
    }

    clearFilter() {
        this.state.date_from = '';
        this.state.date_to = '';
        this.state.branch_id = '';
        this.state.province_id = '';
        this.state.city_id = '';
        this.state.zone_id = '';
        this.state.segment_l1 = '';
        this.state.segment_l2 = '';
        this.state.segment_l3 = '';
        this.state.segment_l4 = '';
        this.state.amount_min = '';
        this.state.amount_max = '';
        
        browser.sessionStorage.removeItem(FILTER_STORAGE_KEY); // <-- CLEAR STORAGE
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