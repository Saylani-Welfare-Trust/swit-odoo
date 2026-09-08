/** @odoo-module */
const { Component } = owl;
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRef, useState } from "@odoo/owl";
import { BlockUI } from "@web/core/ui/block_ui";
import { download } from "@web/core/network/download";
const actionRegistry = registry.category("actions");

class GeneralLedger extends owl.Component {
    setup() {
        super.setup(...arguments);
        this.initial_render = true;
        this.orm = useService('orm');
        this.action = useService('action');
        this.tbody = useRef('tbody');
        this.unfoldButton = useRef('unfoldButton');
        this.state = useState({
            account: [],
            account_data: {},
            account_data_list: null,
            account_total: {},
            total_debit: 0,
            total_credit: 0,
            currency: null,
            journals: [],
            selected_journal_list: [],
            analytics: [],
            selected_analytic_list: [],
            selected_analytic_account_rec: [],
            title: null,
            filter_applied: null,
            account_list: [],
            account_total_list: {},
            date_range: 'month',
            options: {},
            method: {
                'accrual': true
            },
            searchQuery: '',               // NEW
        });
        this.load_data();
        this.searchTimeout = null;
        this.debounceSearch = this.debounceSearch.bind(this);
    }

    // Debounce helper
    debounceSearch(ev) {
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        this.searchTimeout = setTimeout(() => {
            this.applySearch();
        }, 500);
    }

    async applySearch() {
        await this.refreshData();   // just refresh with current search
    }

    clearSearch() {
        this.state.searchQuery = '';
        this.applySearch();
    }

    // ---------- NEW: central data refresh ----------
    async refreshData() {
        let account_list = [];
        let account_totals = {};
        let totalDebitSum = 0;
        let totalCreditSum = 0;
        let currency = null;
        const self = this;

        try {
            const filtered_data = await self.orm.call("account.general.ledger", "get_filter_values", [
                self.state.selected_journal_list,
                self.state.date_range,
                self.state.options,
                self.state.selected_analytic_list,
                self.state.method,
                self.state.searchQuery   // always include search
            ]);
            const raw_data = filtered_data || {};
            self.state.account_data = raw_data;
            $.each(raw_data, function (index, value) {
                if (index !== 'account_totals' && index !== 'journal_ids' && index !== 'analytic_ids') {
                    if (Array.isArray(value) || value && typeof value === 'object') {
                        account_list.push(index);
                    }
                } else if (index === 'journal_ids') {
                    self.state.journals = value || [];
                } else if (index === 'analytic_ids') {
                    self.state.analytics = value || [];
                } else {
                    account_totals = value || {};
                    Object.values(account_totals).forEach(acc => {
                        if (acc && typeof acc === 'object') {
                            currency = acc.currency_id || currency;
                            totalDebitSum += Number(acc.total_debit || 0);
                            totalCreditSum += Number(acc.total_credit || 0);
                        }
                    });
                }
            });
            self.state.account = account_list;
            self.state.account_list = account_list;
            self.state.account_data_list = self.state.account_data;
            self.state.account_total_list = account_totals;
            self.state.account_total = account_totals;
            self.state.currency = currency;
            self.state.total_debit = Number(totalDebitSum || 0).toFixed(2);
            self.state.total_credit = Number(totalCreditSum || 0).toFixed(2);
        } catch (e) {
            // keep previous data or reset
        }
    }

    async load_data() {
        // same as before but now uses refreshData
        let account_list = [];
        let account_totals = {};
        let totalDebitSum = 0;
        let totalCreditSum = 0;
        let currency = null;
        var self = this;
        var action_title = self.props.action.display_name;
        try {
            const filtered_data = await self.orm.call("account.general.ledger", "get_filter_values", [
                this.state.selected_journal_list,
                this.state.date_range,
                this.state.options,
                this.state.selected_analytic_list,
                this.state.method,
                this.state.searchQuery
            ]);
            const raw_data = filtered_data || {};
            self.state.account_data = raw_data;
            $.each(raw_data, function (index, value) {
                if (index !== 'account_totals' && index !== 'journal_ids' && index !== 'analytic_ids') {
                    if (Array.isArray(value) || value && typeof value === 'object') {
                        account_list.push(index);
                    }
                } else if (index === 'journal_ids') {
                    self.state.journals = value || []
                }
                else if (index === 'analytic_ids') {
                    self.state.analytics = value || []
                }
                else {
                    account_totals = value || {}
                    Object.values(account_totals).forEach(account_list => {
                        if (account_list && typeof account_list === 'object') {
                            currency = account_list.currency_id || currency
                            totalDebitSum += Number(account_list.total_debit || 0);
                            totalCreditSum += Number(account_list.total_credit || 0);
                        }
                    });
                }
            })
            self.state.account = account_list
            self.state.account_list = account_list
            self.state.account_data_list = self.state.account_data
            self.state.account_total_list = account_totals
            self.state.account_total = account_totals
            self.state.currency = currency
            self.state.total_debit = Number(totalDebitSum || 0).toFixed(2)
            self.state.total_credit = Number(totalCreditSum || 0).toFixed(2)
            self.state.title = action_title
        }
        catch (el) {
            self.state.account = []
            self.state.account_data = {}
            self.state.account_total = {}
            self.state.currency = null
            self.state.total_debit = '0.00'
            self.state.total_credit = '0.00'
            self.state.title = action_title
        }
    }

    // ---------- applyFilter now only processes UI events and then calls refreshData ----------
    async applyFilter(val, ev, is_delete = false) {
        // Process filter changes from UI events
        if (ev) {
            // handle account selection (unlikely here)
            if (ev.input && ev.input.attributes.placeholder.value == 'Account' && !is_delete) {
                this.state.selected_analytic.push(val[0].id);
                this.state.selected_analytic_account_rec.push(val[0]);
            } else if (is_delete) {
                let index = this.state.selected_analytic_account_rec.indexOf(val);
                this.state.selected_analytic_account_rec.splice(index, 1);
                this.state.selected_analytic = this.state.selected_analytic_account_rec.map((rec) => rec.id);
            }
        } else {
            // val is a DOM event from a button or input
            if (val.target.name === 'start_date') {
                this.state.date_range = {
                    ...this.state.date_range,
                    start_date: val.target.value
                };
            } else if (val.target.name === 'end_date') {
                this.state.date_range = {
                    ...this.state.date_range,
                    end_date: val.target.value
                };
            } else if (val.target.attributes && val.target.attributes["data-value"]) {
                const dataValue = val.target.attributes["data-value"].value;
                if (['month', 'year', 'quarter', 'last-month', 'last-year', 'last-quarter'].includes(dataValue)) {
                    this.state.date_range = dataValue;
                } else if (dataValue === 'journal') {
                    const journalId = parseInt(val.target.attributes["data-id"].value, 10);
                    if (!val.target.classList.contains("selected-filter")) {
                        this.state.selected_journal_list.push(journalId);
                        val.target.classList.add("selected-filter");
                    } else {
                        this.state.selected_journal_list = this.state.selected_journal_list.filter(id => id !== journalId);
                        val.target.classList.remove("selected-filter");
                    }
                } else if (dataValue === 'analytic') {
                    const analyticId = parseInt(val.target.attributes["data-id"].value, 10);
                    if (!val.target.classList.contains("selected-filter")) {
                        this.state.selected_analytic_list.push(analyticId);
                        val.target.classList.add("selected-filter");
                    } else {
                        this.state.selected_analytic_list = this.state.selected_analytic_list.filter(id => id !== analyticId);
                        val.target.classList.remove("selected-filter");
                    }
                } else if (dataValue === 'draft') {
                    if (val.target.classList.contains("selected-filter")) {
                        const { draft, ...updated } = this.state.options;
                        this.state.options = updated;
                        val.target.classList.remove("selected-filter");
                    } else {
                        this.state.options = { ...this.state.options, 'draft': true };
                        val.target.classList.add("selected-filter");
                    }
                } else if (dataValue === 'cash-basis') {
                    if (val.target.classList.contains("selected-filter")) {
                        const { cash, ...updated } = this.state.method;
                        this.state.method = { ...updated, 'accrual': true };
                        val.target.classList.remove("selected-filter");
                    } else {
                        const { accrual, ...updated } = this.state.method;
                        this.state.method = { ...updated, 'cash': true };
                        val.target.classList.add("selected-filter");
                    }
                }
            }
        }
        // After processing UI changes, refresh the data
        await this.refreshData();

        // Remove unfoldAll highlight if any
        if (this.unfoldButton && this.unfoldButton.el && $(this.unfoldButton.el).find(".selected-filter").length) {
            this.unfoldButton.el.classList.remove("selected-filter");
        }
    }

    async unfoldAll(ev) {
        if (!ev.target.classList.contains("selected-filter")) {
            for (var length = 0; length < this.tbody.el.children.length; length++) {
                $(this.tbody.el.children[length])[0].classList.add('show')
            }
            ev.target.classList.add("selected-filter");
        } else {
            for (var length = 0; length < this.tbody.el.children.length; length++) {
                $(this.tbody.el.children[length])[0].classList.remove('show')
            }
            ev.target.classList.remove("selected-filter");
        }
    }

    filter() {
    var self=this;
    let startDate, endDate;
    let startYear, startMonth, startDay, endYear, endMonth, endDay;
        if (self.state.date_range){
            const today = new Date();
            if (self.state.date_range === 'year') {
                startDate = new Date(today.getFullYear(), 0, 1);
                endDate = new Date(today.getFullYear(), 11, 31);
            } else if (self.state.date_range === 'quarter') {
                const currentQuarter = Math.floor(today.getMonth() / 3);
                startDate = new Date(today.getFullYear(), currentQuarter * 3, 1);
                endDate = new Date(today.getFullYear(), (currentQuarter + 1) * 3, 0);
            } else if (self.state.date_range === 'month') {
                startDate = new Date(today.getFullYear(), today.getMonth(), 1);
                endDate = new Date(today.getFullYear(), today.getMonth() + 1, 0);
            } else if (self.state.date_range === 'last-month') {
                startDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                endDate = new Date(today.getFullYear(), today.getMonth(), 0);
            } else if (self.state.date_range === 'last-year') {
                startDate = new Date(today.getFullYear() - 1, 0, 1);
                endDate = new Date(today.getFullYear() - 1, 11, 31);
            } else if (self.state.date_range === 'last-quarter') {
                const lastQuarter = Math.floor((today.getMonth() - 3) / 3);
                startDate = new Date(today.getFullYear(), lastQuarter * 3, 1);
                endDate = new Date(today.getFullYear(), (lastQuarter + 1) * 3, 0);
            }
            else{
                startDate = new Date(self.state.date_range.start_date);
                endDate = new Date(self.state.date_range.end_date);
            }
        // Get the date components for start and end dates
        if (startDate) {
        startYear = startDate.getFullYear();
        startMonth = startDate.getMonth() + 1;
        startDay = startDate.getDate();
        }
        if (endDate) {
        endYear = endDate.getFullYear();
        endMonth = endDate.getMonth() + 1;
        endDay = endDate.getDate();
        }
        }
        const journals = self.state.journals || [];
        const analytics = self.state.analytics || [];
        const selectedJournalIDs = Object.values(self.state.selected_journal_list || []);
        const selectedJournalNames = selectedJournalIDs.map((journalID) => {
          const journal = journals.find((journal) => journal.id === journalID);
          return journal ? journal.name : '';
        });
        const selectedAnalyticIDs = Object.values(self.state.selected_analytic_list || []);
        const selectedAnalyticNames = selectedAnalyticIDs.map((analyticID) => {
          const analytic = analytics.find((analytic) => analytic.id === analyticID);
          return analytic ? analytic.name : '';
        });
        let filters = {
            'journal': selectedJournalNames,
            'analytic': selectedAnalyticNames,
            'account': self.state.selected_analytic_account_rec,
            'options': self.state.options,
            'start_date': null,
            'end_date': null,
        };
        // Check if start and end dates are available before adding them to the filters object
        if (startYear !== undefined && startMonth !== undefined && startDay !== undefined &&
            endYear !== undefined && endMonth !== undefined && endDay !== undefined) {
            filters['start_date'] = `${startYear}-${startMonth < 10 ? '0' : ''}${startMonth}-${startDay < 10 ? '0' : ''}${startDay}`;
            filters['end_date'] = `${endYear}-${endMonth < 10 ? '0' : ''}${endMonth}-${endDay < 10 ? '0' : ''}${endDay}`;
        }
        return filters
    }
}
GeneralLedger.defaultProps = {
    resIds: [],
};
GeneralLedger.template = 'gl_template_new';
actionRegistry.add("gen_l", GeneralLedger);