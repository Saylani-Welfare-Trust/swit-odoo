/** @odoo-module */
const { Component } = owl;
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRef, useState, onMounted } from "@odoo/owl";
import { BlockUI } from "@web/core/ui/block_ui";
import { download } from "@web/core/network/download";
const actionRegistry = registry.category("actions");

class GeneralLedger extends owl.Component {

    formatAmount(value) {
        const num = Number(value || 0);
        return num.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    setup() {
        super.setup(...arguments);
        this.initial_render = true;
        this.orm    = useService('orm');
        this.action = useService('action');
        this.tbody  = useRef('tbody');
        this.unfoldButton  = useRef('unfoldButton');
        this.gl_start_date = useRef('gl_start_date');
        this.gl_end_date   = useRef('gl_end_date');

        // ---- Inherit filters from the action that opened this GL ----
        const params = (this.props.action && this.props.action.params) || {};

        const incomingDateRange  = params.default_date_range || 'month';
        const incomingJournals   = Array.isArray(params.default_journal_ids)
            ? params.default_journal_ids : [];
        const incomingAccounts   = Array.isArray(params.default_account_names)
            ? params.default_account_names : [];
        const incomingOptions    = params.default_options || {};
        const incomingMethod     = (params.default_method &&
                                    Object.keys(params.default_method).length)
            ? { ...params.default_method } : { accrual: true };

        this.state = useState({
            account: [],
            account_data: {},
            account_data_list: null,
            account_total: {},
            total_debit: 0,
            total_credit: 0,
            currency: null,

            journals: [],
            selected_journal_list: [...incomingJournals],

            analytics: [],
            selected_analytic_list: [],
            selected_analytic_account_rec: [],

            selected_account_list: [...incomingAccounts],
            all_accounts: [],
            account_from: '',
            account_to: '',

            title: null,
            filter_applied: null,
            account_list: [],
            account_total_list: {},

            date_range: incomingDateRange,
            options: { ...incomingOptions },
            method: { ...incomingMethod },

            search_query: '',
            account_list_full: [],
            account_data_full: {},
            collapsed_accounts: {},
        });
        this.searchTimeout = null;

        onMounted(() => {
            // Reflect the inherited date range in the visible inputs
            if (typeof incomingDateRange === 'object') {
                if (this.gl_start_date?.el && incomingDateRange.start_date) {
                    this.gl_start_date.el.value = incomingDateRange.start_date;
                }
                if (this.gl_end_date?.el && incomingDateRange.end_date) {
                    this.gl_end_date.el.value = incomingDateRange.end_date;
                }
            }
        });

        this.load_data();
    }

    async load_data() {
        let account_list = [];
        let account_totals = {};
        let totalDebitSum = 0;
        let totalCreditSum = 0;
        let currency = null;
        var self = this;
        var action_title = self.getActionTitle();
        try {
            const filtered_data = await self.orm.call("account.general.ledger", "get_filter_values", [this.state.selected_journal_list, this.state.date_range, this.state.options, this.state.selected_analytic_list, this.state.method]);
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
            // sort accounts A -> Z (case-insensitive, numeric-aware)
            account_list = self.sortAccounts(account_list);
            self.state.account = account_list
            self.state.account_list = account_list
            self.state.account_data_list = self.state.account_data
            self.state.account_list_full = [...account_list];
            self.state.all_accounts = [...account_list];
            self.state.account_data_full = { ...self.state.account_data };
            self.state.account_total_list = account_totals
            self.state.account_total = account_totals
            self.state.currency = currency
            self.state.total_debit = Number(totalDebitSum || 0).toFixed(2)
            self.state.total_credit = Number(totalCreditSum || 0).toFixed(2)
            self.state.title = action_title
            const collapsed = {};
            account_list.forEach((acc) => { collapsed[acc] = true; });
            self.state.collapsed_accounts = collapsed;
            if (self.state.selected_account_list.length) {
                self.applySearch();
            }
        }
        catch (el) {
            self.state.account = []
            self.state.account_data = {}
            self.state.account_total = {}
            self.state.currency = null
            self.state.total_debit = '0.00'
            self.state.total_credit = '0.00'
            self.state.title = action_title
            self.state.collapsed_accounts = {};
        }
    }
    async printPdf(ev) {
        ev.preventDefault();
        var self = this;
        let totals = {
            'total_debit': this.state.total_debit,
            'total_credit': this.state.total_credit,
            'currency': this.state.currency,
        }
        var action_title = self.getActionTitle();
        return self.action.doAction({
            'type': 'ir.actions.report',
            'report_type': 'qweb-pdf',
            'report_name': 'dynamic_accounts_report.general_ledger',
            'report_file': 'dynamic_accounts_report.general_ledger',
            'data': {
                'report_options': {
                    'journal_ids': self.state.selected_journal_list || [],
                    'date_range': self.state.date_range || 'month',
                    'options': self.state.options || {},
                    'analytic_ids': self.state.selected_analytic_list || [],
                    'method': self.state.method || { 'accrual': true },
                },
                'title': action_title,
                'filters': this.filter(),
                'grand_total': totals,
                'report_name': action_title
            },
            'display_name': action_title,
        });
    }
    async print_xlsx() {
        var self = this;
        let totals = {
            'total_debit': this.state.total_debit,
            'total_credit': this.state.total_credit,
            'currency': this.state.currency,
        }
        var action_title = self.getActionTitle();
        var datas = {
            'account': self.state.account,
            'data': self.state.account_data,
            'total': self.state.account_total,
            'title': action_title,
            'filters': this.filter(),
            'grand_total': totals,
        }
        var action = {
            'data': {
                'model': 'account.general.ledger',
                'data': JSON.stringify(datas),
                'output_format': 'xlsx',
                'report_action': self.getActionXmlId(),
                'report_name': action_title,
            },
        };
        BlockUI;
        await download({
            url: '/xlsx_report',
            data: action.data,
            complete: () => unblockUI,
            error: (error) => self.call('crash_manager', 'rpc_error', error),
        });
    }

    getActionTitle() {
        const params = (this.props.action && this.props.action.params) || {};
        return params.default_title
            || (this.props.action && (this.props.action.display_name || this.props.action.name))
            || 'General Ledger';
    }

    /* --------------------------------------------------------------------
    * Account code range filter (From / To)
    * ------------------------------------------------------------------ */

    _extractAccountCode(acc) {
        // Pull the leading numeric code out of the account label.
        // Handles "1010 Cash", "1010 - Cash", "1010-Cash", "1010".
        const s = String(acc ?? '').trim();
        const m = s.match(/^(\d+)/);
        return m ? m[1] : '';
    }

    applyAccountRange() {
        const from = (this.state.account_from || '').trim();
        const to   = (this.state.account_to   || '').trim();

        if (!from && !to) {
            return;
        }

        const inRange = (acc) => {
            const code = this._extractAccountCode(acc);
            if (!code) {
                return false;
            }
            // Left-pad so "99" < "101" compares numerically, not lexically
            const width = Math.max(code.length, from.length, to.length);
            const pad   = (v) => String(v).padStart(width, '0');
            const c     = pad(code);
            if (from && c < pad(from)) { return false; }
            if (to   && c > pad(to))   { return false; }
            return true;
        };

        // ⬇⬇ KEY CHANGE: REPLACE, don't union ⬇⬇
        const selected = (this.state.all_accounts || []).filter(inRange);
        this.state.selected_account_list = selected;

        // Sync highlight on every account button in the dropdown
        document
            .querySelectorAll(".report-filter-button[data-value='account']")
            .forEach((btn) => {
                const id = btn.getAttribute('data-id');
                btn.classList.toggle('selected-filter', selected.includes(id));
            });

        this.applySearch();
    }

    clearAccountRange() {
        this.state.account_from = '';
        this.state.account_to   = '';
    }
    getActionXmlId() {
        return (this.props.action && this.props.action.xml_id)
            || 'dynamic_accounts_report.action_general_ledger';
    }
    getAccountTotals(account) {
        if (!this.state.account_total || !this.state.account_total[account]) {
            return {};
        }
        return this.state.account_total[account];
    }
    getAccountTotalValue(account, key, fallback = 0) {
        const totals = this.getAccountTotals(account);
        return totals && totals[key] !== undefined && totals[key] !== null ? totals[key] : fallback;
    }
    getAccountData(account) {
        if (!this.state.account_data || !this.state.account_data[account]) {
            return [];
        }
        return this.state.account_data[account];
    }
    isAccountCollapsed(account) {
        return !!this.state.collapsed_accounts[account];
    }
    toggleAccount(account) {
        this.state.collapsed_accounts = {
            ...this.state.collapsed_accounts,
            [account]: !this.state.collapsed_accounts[account],
        };
    }
    gotoJournalEntry(ev) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: 'account.move',
            res_id: parseInt(ev.target.attributes["data-id"].value, 10),
            views: [[false, "form"]],
            target: "current",
        });
    }
    gotoJournalItem(ev) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: 'account.move.line',
            name: "Journal Items",
            views: [[false, "list"]],
            domain: [["account_id", "=", parseInt(ev.target.attributes["data-id"].value, 10)]],
            target: "current",
        });
    }
    getDomain() {
        return [];
    }

    async applyFilter(val, ev, is_delete = false) {
        let account_list = []
        let account_totals = ''
        let totalDebitSum = 0;
        let totalCreditSum = 0;
        this.state.account = null
        this.state.account_data = null
        this.state.account_total = null
        this.state.filter_applied = true;
        if (this.state.selected_account_list.length) {
            this.applySearch();
        }
        if (ev) {
            if (ev.input && ev.input.attributes.placeholder.value == 'Account' && !is_delete) {
                this.state.selected_analytic.push(val[0].id)
                this.state.selected_analytic_account_rec.push(val[0])
            } else if (is_delete) {
                let index = this.state.selected_analytic_account_rec.indexOf(val)
                this.state.selected_analytic_account_rec.splice(index, 1)
                this.state.selected_analytic = this.state.selected_analytic_account_rec.map((rec) => rec.id)
            }
        }
        else {
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
            } else if (val.target.attributes["data-value"].value == 'month') {
                this.state.date_range = val.target.attributes["data-value"].value
            } else if (val.target.attributes["data-value"].value == 'year') {
                this.state.date_range = val.target.attributes["data-value"].value
            } else if (val.target.attributes["data-value"].value == 'quarter') {
                this.state.date_range = val.target.attributes["data-value"].value
            } else if (val.target.attributes["data-value"].value == 'last-month') {
                this.state.date_range = val.target.attributes["data-value"].value
            } else if (val.target.attributes["data-value"].value == 'last-year') {
                this.state.date_range = val.target.attributes["data-value"].value
            } else if (val.target.attributes["data-value"].value == 'last-quarter') {
                this.state.date_range = val.target.attributes["data-value"].value
            }
            else if (val.target.attributes["data-value"].value == 'journal') {
                if (!val.target.classList.contains("selected-filter")) {
                    this.state.selected_journal_list.push(parseInt(val.target.attributes["data-id"].value, 10))
                    val.target.classList.add("selected-filter");
                } else {
                    const updatedList = this.state.selected_journal_list.filter(item => item !== parseInt(val.target.attributes["data-id"].value, 10));
                    this.state.selected_journal_list = updatedList
                    val.target.classList.remove("selected-filter");
                }
            }
            else if (val.target.attributes["data-value"].value == 'analytic') {
                if (!val.target.classList.contains("selected-filter")) {
                    this.state.selected_analytic_list.push(parseInt(val.target.attributes["data-id"].value, 10))
                    val.target.classList.add("selected-filter");
                } else {
                    const updatedList = this.state.selected_analytic_list.filter(item => item !== parseInt(val.target.attributes["data-id"].value, 10));
                    this.state.selected_analytic_list = updatedList
                    val.target.classList.remove("selected-filter");
                }
            }
            else if (val.target.attributes["data-value"].value === 'draft') {
                if (val.target.classList.contains("selected-filter")) {
                    const { draft, ...updatedAccount } = this.state.options;
                    this.state.options = updatedAccount;
                    val.target.classList.remove("selected-filter");
                } else {
                    this.state.options = {
                        ...this.state.options,
                        'draft': true
                    };
                    val.target.classList.add("selected-filter");
                }
            } else if (val.target.attributes["data-value"].value === 'cash-basis') {
                if (val.target.classList.contains("selected-filter")) {
                    const { cash, ...updatedAccount } = this.state.method;
                    this.state.method = updatedAccount;
                    this.state.method = {
                        ...this.state.method,
                        'accrual': true
                    }
                    val.target.classList.remove("selected-filter");
                } else {
                    const { accrual, ...updatedAccount } = this.state.method;
                    this.state.method = updatedAccount;
                    this.state.method = {
                        ...this.state.method,
                        'cash': true
                    };
                    val.target.classList.add("selected-filter");
                }
            }
        }
        let filtered_data = await this.orm.call("account.general.ledger", "get_filter_values", [this.state.selected_journal_list, this.state.date_range, this.state.options, this.state.selected_analytic_list, this.state.method]);
        filtered_data = filtered_data || {};
        $.each(filtered_data, function (index, value) {
            if (index !== 'account_totals' && index !== 'journal_ids' && index !== 'analytic_ids') {
                if (Array.isArray(value) || value && typeof value === 'object') {
                    account_list.push(index)
                }
            }
            else {
                account_totals = value || {}
                Object.values(account_totals).forEach(account_list => {
                    if (account_list && typeof account_list === 'object') {
                        totalDebitSum += Number(account_list.total_debit || 0);
                        totalCreditSum += Number(account_list.total_credit || 0);
                    }
                });
            }
        })
        // sort accounts A -> Z (case-insensitive, numeric-aware)
        account_list = this.sortAccounts(account_list);
        this.state.account = account_list
        this.state.account_data = filtered_data
        this.state.account_list_full = [...account_list];
        this.state.all_accounts = [...account_list];
        this.state.account_data_full = { ...filtered_data };
        this.state.account_total = account_totals
        this.state.total_debit = Number(totalDebitSum || 0).toFixed(2)
        this.state.total_credit = Number(totalCreditSum || 0).toFixed(2)
        const collapsed = {};
        account_list.forEach((acc) => { collapsed[acc] = true; });
        this.state.collapsed_accounts = collapsed;
        if (this.unfoldButton && this.unfoldButton.el && $(this.unfoldButton.el.classList).find("selected-filter")) {
            this.unfoldButton.el.classList.remove("selected-filter")
        }
    }

    onSearchInput(ev) {
        const value = ev.target.value;
        this.state.search_query = value;
        clearTimeout(this.searchTimeout);
        // debounce so we don't re-filter on every keystroke while typing fast
        this.searchTimeout = setTimeout(() => {
            this.applySearch();
        }, 300);
    }

    applySearch() {
        const query = (this.state.search_query || '').trim().toLowerCase();
        const accFilter = this.state.selected_account_list || [];

        // Base accounts: all, or only those picked in the Account dropdown
        let baseAccounts = this.state.account_list_full;
        if (accFilter.length) {
            baseAccounts = baseAccounts.filter((acc) => accFilter.includes(acc));
        }

        // No search query → return base accounts, all collapsed
        if (!query) {
            const filteredData = {};
            const collapsed = {};
            baseAccounts.forEach((acc) => {
                filteredData[acc] = this.state.account_data_full[acc] || [];
                collapsed[acc] = true;
            });
            this.state.account = baseAccounts;
            this.state.account_data = filteredData;
            this.state.collapsed_accounts = collapsed;
            return;
        }

        // Token-based search
        const queryTokens = query.split(/\s+/).filter(Boolean);
        const matchesAllTokens = (haystack) =>
            queryTokens.every((token) => haystack.includes(token));

        // ---------- Pass 1: match by ACCOUNT NAME ----------
        const accountNameMatches = baseAccounts.filter((account) =>
            matchesAllTokens(account.toLowerCase())
        );

        if (accountNameMatches.length) {
            const filteredData = {};
            const collapsed = {};
            const expandSingle = accountNameMatches.length === 1;
            for (const account of accountNameMatches) {
                filteredData[account] = this.state.account_data_full[account] || [];
                collapsed[account] = !expandSingle;
            }
            this.state.account = accountNameMatches;
            this.state.account_data = filteredData;
            this.state.collapsed_accounts = collapsed;
            return;
        }

        // ---------- Pass 2: match by LINE content (no split_account) ----------
        const matchedAccounts = [];
        const filteredData = {};
        const collapsed = {};
        for (const account of baseAccounts) {
            const lines = this.state.account_data_full[account] || [];
            const matchingLines = lines.filter((line) => {
                const partner = line.partner_id;
                const partnerName = Array.isArray(partner) ? partner[1] : '';
                const haystack = [
                    line.move_name || '',
                    line.name || '',
                    partnerName,
                    line.ref || '',
                    line.trx_type || '',
                    line.location || '',
                ].join(' ').toLowerCase();
                return matchesAllTokens(haystack);
            });
            if (matchingLines.length) {
                matchedAccounts.push(account);
                filteredData[account] = matchingLines;
                collapsed[account] = true;
            }
        }
        this.state.account = matchedAccounts;
        this.state.account_data = filteredData;
        this.state.collapsed_accounts = collapsed;
    }

    async applyAccountFilter(ev) {
        const accName = ev.target.attributes["data-id"].value;
        let selected = [...this.state.selected_account_list];

        if (selected.includes(accName)) {
            selected = selected.filter((a) => a !== accName);
            ev.target.classList.remove("selected-filter");
        } else {
            selected.push(accName);
            ev.target.classList.add("selected-filter");
        }
        this.state.selected_account_list = selected;
        this.applySearch();
    }

    sortAccounts(accounts) {
        return [...(accounts || [])].sort((a, b) =>
            String(a ?? '').localeCompare(String(b ?? ''), undefined, {
                sensitivity: 'base', // case-insensitive: "abc" and "ABC" grouped together
                numeric: true,       // so "Account 2" comes before "Account 10"
            })
        );
    }
    clearAccountFilter() {
        this.state.selected_account_list = [];
        this.state.account_from = '';
        this.state.account_to   = '';
        document
            .querySelectorAll(".report-filter-button[data-value='account']")
            .forEach((btn) => btn.classList.remove("selected-filter"));
        this.applySearch();
    }
    async unfoldAll(ev) {
        const shouldCollapseAll = !ev.target.classList.contains("selected-filter");
        const updated = {};
        for (const account of this.state.account || []) {
            updated[account] = shouldCollapseAll;
        }
        this.state.collapsed_accounts = updated;
        ev.target.classList.toggle("selected-filter");
    }
    filter() {
        var self = this;
        let startDate, endDate;
        let startYear, startMonth, startDay, endYear, endMonth, endDay;
        if (self.state.date_range) {
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
            else {
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