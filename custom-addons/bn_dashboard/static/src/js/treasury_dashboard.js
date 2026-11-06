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
            comparison_mode: savedFilters.comparison_mode || 'month',
            comparison_period1: savedFilters.comparison_period1 || '',
            comparison_period2: savedFilters.comparison_period2 || '',
            comparison_result: {},
        });

        onWillStart(async () => {
            this._init_comparison_periods();
            await this.fetchData();
            await this.fetchComparison();
        });
    }

    _init_comparison_periods() {
        const today = new Date();
        if (this.state.comparison_mode === 'year') {
            if (!this.state.comparison_period1) {
                this.state.comparison_period1 = String(today.getFullYear() - 1);
            }
            if (!this.state.comparison_period2) {
                this.state.comparison_period2 = String(today.getFullYear());
            }
        } else {
            const fmt_m = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
            if (!this.state.comparison_period1) {
                this.state.comparison_period1 = fmt_m(new Date(today.getFullYear(), today.getMonth() - 1, 1));
            }
            if (!this.state.comparison_period2) {
                this.state.comparison_period2 = fmt_m(today);
            }
        }
    }

    async onchange_comparison_mode() {
        // Reset periods when the mode switches
        this.state.comparison_period1 = '';
        this.state.comparison_period2 = '';
        this._init_comparison_periods();
        await this.fetchComparison();
    }

    async fetchComparison() {
        try {
            let eff_seg = null;
            if (this.state.segment_l4) eff_seg = parseInt(this.state.segment_l4, 10);
            else if (this.state.segment_l3) eff_seg = parseInt(this.state.segment_l3, 10);
            else if (this.state.segment_l2) eff_seg = parseInt(this.state.segment_l2, 10);
            else if (this.state.segment_l1) eff_seg = parseInt(this.state.segment_l1, 10);

            const data = await this.env.services.rpc("/treasury/dashboard/comparison", {
                mode: this.state.comparison_mode,
                period1: this.state.comparison_period1,
                period2: this.state.comparison_period2,
                analytic_account_id: this.state.branch_id ? parseInt(this.state.branch_id, 10) : null,
                province_id: this.state.province_id ? parseInt(this.state.province_id, 10) : null,
                city_id: this.state.city_id ? parseInt(this.state.city_id, 10) : null,
                zone_id: this.state.zone_id ? parseInt(this.state.zone_id, 10) : null,
                segment_id: eff_seg,
                amount_min: this.state.amount_min ? parseFloat(this.state.amount_min) : null,
                amount_max: this.state.amount_max ? parseFloat(this.state.amount_max) : null,
            });
            this.state.comparison_result = data.models || {};
        } catch (error) {
            console.error("Comparison Fetch Error:", error);
        }
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
            comparison_mode: this.state.comparison_mode,
            comparison_period1: this.state.comparison_period1,
            comparison_period2: this.state.comparison_period2,
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

    // Add `restriction: null` to your state initialization at the top.

    async fetchData() {
        try {
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
            
            this.state.currency = data.currency;
            this.state.cheques = { ...this.state.cheques, ...data.cheques };
            this.state.deposits = { ...this.state.deposits, ...data.deposits };
            this.state.transfers = { ...this.state.transfers, ...data.transfers };
            
            this.state.restriction = data.restriction || null;
            let needsRefresh = false;

            // ⚡ FILTER DROPDOWNS AND AUTO-SELECT
            let provinces = data.provinces || [];
            let cities = data.cities || [];
            let zones = data.zones || [];
            let analytic_accounts = data.analytic_accounts || [];

            if (this.state.restriction) {
                const allowedProvs = this.state.restriction.provinces || [];
                const allowedIds = this.state.restriction.analytic_ids || [];

                if (allowedProvs.length) {
                    provinces = provinces.filter(p => allowedProvs.includes(p.id));
                    if (provinces.length === 1 && !this.state.province_id) {
                        this.state.province_id = provinces[0].id;
                        needsRefresh = true;
                    }
                }
                if (allowedIds.length) {
                    cities = cities.filter(c => allowedIds.includes(c.id) || allowedIds.includes(c.province_id));
                    zones = zones.filter(z => allowedIds.includes(z.id) || allowedIds.includes(z.city_id));
                    analytic_accounts = analytic_accounts.filter(a => allowedIds.includes(a.id) || allowedIds.includes(a.zone_id));
                    
                    // Auto-select city if restricted to exactly 1
                    if (cities.length === 1 && !this.state.city_id) {
                        this.state.city_id = cities[0].id;
                        if (cities[0].province_id) this.state.province_id = cities[0].province_id;
                        needsRefresh = true;
                    }
                }
            }

            this.state.analytic_accounts = analytic_accounts;
            this.state.provinces = provinces;
            this.state.cities = cities;
            this.state.zones = zones;
            this.state.segments_l1 = data.segments_l1 || [];
            this.state.segments_l2 = data.segments_l2 || [];
            this.state.segments_l3 = data.segments_l3 || [];
            this.state.segments_l4 = data.segments_l4 || [];

            if (needsRefresh) {
                await this.fetchData();
            }
            
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
        this.save_filters();
        await this.fetchData();
        await this.fetchComparison();
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

    // ------------------------------------------------------------------
    // Build the domain that mirrors the dashboard's current filters
    // ------------------------------------------------------------------
    getFilterDomain(model) {
        const domain = [];

        const bid = this.state.branch_id   ? parseInt(this.state.branch_id, 10)   : null;
        const pid = this.state.province_id ? parseInt(this.state.province_id, 10) : null;
        const cid = this.state.city_id     ? parseInt(this.state.city_id, 10)     : null;
        const zid = this.state.zone_id     ? parseInt(this.state.zone_id, 10)     : null;

        // Effective segment (deepest non-empty level)
        let seg_id = null;
        if (this.state.segment_l4)      seg_id = parseInt(this.state.segment_l4, 10);
        else if (this.state.segment_l3) seg_id = parseInt(this.state.segment_l3, 10);
        else if (this.state.segment_l2) seg_id = parseInt(this.state.segment_l2, 10);
        else if (this.state.segment_l1) seg_id = parseInt(this.state.segment_l1, 10);

        // Analytic filter — apply ALL non-empty filters, mirroring the backend
        if (bid)    domain.push(['analytic_account_id', '=', bid]);
        if (pid)    domain.push(['analytic_account_id', 'child_of', pid]);
        if (cid)    domain.push(['analytic_account_id', 'child_of', cid]);
        if (zid)    domain.push(['analytic_account_id', 'child_of', zid]);
        if (seg_id) domain.push(['analytic_account_id', 'child_of', seg_id]);

        // Date field per model — match what the backend actually uses
        const DATE_FIELD = {
            'pos.cheque': 'date',
            'direct.deposit': 'create_date',  
            'journal.transfer': 'date',
        }[model] || 'date';

        if (this.state.date_from) domain.push([DATE_FIELD, '>=', this.state.date_from]);
        if (this.state.date_to)   domain.push([DATE_FIELD, '<=', this.state.date_to]);

        // Amount filter
        if (this.state.amount_min) domain.push(['amount', '>=', parseFloat(this.state.amount_min)]);
        if (this.state.amount_max) domain.push(['amount', '<=', parseFloat(this.state.amount_max)]);

        return domain;
    }

    async refresh() {
        await this.fetchData();
    }


    // ------------------------------------------------------------------
    // Open a list view with the dashboard filters automatically applied
    // ------------------------------------------------------------------
    openCustomModel(modelName, extraDomain = []) {
        const fullDomain = [...extraDomain, ...this.getFilterDomain(modelName)];
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: modelName,
            views: [[false, 'list'], [false, 'form']],
            domain: fullDomain,
            target: 'current',
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