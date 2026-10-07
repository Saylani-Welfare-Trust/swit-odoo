/** @odoo-module */
const { Component } = owl;
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRef, useState } from "@odoo/owl";
import { BlockUI } from "@web/core/ui/block_ui";
import { download } from "@web/core/network/download";
const actionRegistry = registry.category("actions");
import { onMounted } from "@odoo/owl";
const today = luxon.DateTime.now();
let monthNamesShort = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

class PeriodBalance extends owl.Component {
    async setup() {
        super.setup(...arguments);
        this.orm = useService('orm');
        this.action = useService('action');
        this.tbody = useRef('tbody');
        this.end_date = useRef('date_to');
        this.start_date = useRef('date_from');
        this.period = useRef('periods');
        this.period_year = useRef('period_year');

        this.state = useState({
            data: null,
            journals: null,
            accounts: [],
            selected_analytic: [],
            selected_journal_list: [],
            selected_analytic_account_rec: [],
            date_range: 'month',
            date_type: 'month',
            apply_comparison: false,
            comparison_type: null,
            date_viewed: [],
            comparison_number: null,
            options: null,
            method: { 'accural': true },
            collapsed_groups: {},
            collapsed_internal_groups: {},
        });
        onMounted(() => this.load_data());
    }

    async load_data() {
        if (!this.start_date?.el || !this.end_date?.el) return;
        const t = new Date();
        const s = new Date(t.getFullYear(), t.getMonth(), 1);
        const e = new Date(t.getFullYear(), t.getMonth() + 1, 0);
        this.start_date.el.value = this._fmt(s);
        this.end_date.el.value = this._fmt(e);
        this.state.date_viewed = [monthNamesShort[t.getMonth()] + '  ' + t.getFullYear()];

        this.state.accounts = await this.orm.searchRead(
            "account.account", [], ["code", "name", "display_name"], { order: "code" });

        this.state.data = await this.orm.call("account.period.balance", "view_report", []);
        this.state.journals = (this.state.data[0] || {}).journal_ids || [];
    }

    _fmt(d) {
        return d.getFullYear() + '-' +
            String(d.getMonth() + 1).padStart(2, '0') + '-' +
            String(d.getDate()).padStart(2, '0');
    }

    async applyFilter(val, ev, is_delete) {
        if (ev && ev.target && ev.target.attributes["data-value"] &&
            ev.target.attributes["data-value"].value == 'no comparison') {
            const lastIndex = this.state.date_viewed.length - 1;
            this.state.date_viewed.splice(0, lastIndex);
        }
        if (!this.start_date.el?.value || !this.end_date.el?.value) return;

        if (ev) {
            if (ev.input && ev.input.attributes.placeholder.value == 'Account' && !is_delete) {
                this.state.selected_analytic.push(val[0].id)
                this.state.selected_analytic_account_rec.push(val[0])
            } else if (is_delete) {
                let index = this.state.selected_analytic_account_rec.indexOf(val)
                this.state.selected_analytic_account_rec.splice(index, 1)
                this.state.selected_analytic = this.state.selected_analytic_account_rec.map((rec) => rec.id)
            }
        } else {
            const dv = val && val.target.attributes["data-value"] ? val.target.attributes["data-value"].value : null;
            if (val && val.target.name === 'start_date') {
                this.state.date_viewed = []
                this.state.date_viewed.push('From ' + this.formatDate(this.start_date.el.value) + ' To ' + this.formatDate(this.end_date.el.value))
                this.state.date_range = { ...this.state.date_range, start_date: val.target.value };
            } else if (val && val.target.name === 'end_date') {
                this.state.date_viewed = []
                this.state.date_viewed.push('From ' + this.formatDate(this.start_date.el.value) + ' To ' + this.formatDate(this.end_date.el.value))
                this.state.date_range = { ...this.state.date_range, end_date: val.target.value };
            } else if (dv == 'month') {
                this.start_date.el.value = today.startOf('month').toFormat('yyyy-MM-dd')
                this.end_date.el.value = today.endOf('month').toFormat('yyyy-MM-dd')
                this.state.date_viewed = [today.monthShort + ' ' + today.c.year]
                this.state.date_type = 'month'; this.state.comparison_type = 'month'
                this.state.date_range = { start_date: this.start_date.el.value, end_date: this.end_date.el.value };
            } else if (dv == 'year') {
                this.start_date.el.value = today.startOf('year').toFormat('yyyy-MM-dd')
                this.end_date.el.value = today.endOf('year').toFormat('yyyy-MM-dd')
                this.state.date_viewed = [today.c.year]
                this.state.date_type = 'year'; this.state.comparison_type = 'year'
                this.state.date_range = { start_date: this.start_date.el.value, end_date: this.end_date.el.value };
            } else if (dv == 'quarter') {
                this.start_date.el.value = today.startOf('quarter').toFormat('yyyy-MM-dd')
                this.end_date.el.value = today.endOf('quarter').toFormat('yyyy-MM-dd')
                this.state.date_viewed = ['Q ' + today.quarter]
                this.state.date_type = 'quarter'; this.state.comparison_type = 'quarter'
                this.state.date_range = { start_date: this.start_date.el.value, end_date: this.end_date.el.value };
            } else if (dv == 'last-month') {
                const lm = today.startOf('month').minus({ days: 1 });
                this.start_date.el.value = lm.startOf('month').toFormat('yyyy-MM-dd')
                this.end_date.el.value = lm.toFormat('yyyy-MM-dd')
                this.state.date_viewed = [lm.monthShort + ' ' + lm.c.year]
                this.state.date_type = 'month'; this.state.comparison_type = 'month'
                this.state.date_range = { start_date: this.start_date.el.value, end_date: this.end_date.el.value };
            } else if (dv == 'last-year') {
                const ly = today.startOf('year').minus({ days: 1 });
                this.start_date.el.value = ly.startOf('year').toFormat('yyyy-MM-dd')
                this.end_date.el.value = ly.toFormat('yyyy-MM-dd')
                this.state.date_viewed = [ly.c.year]
                this.state.date_type = 'year'; this.state.comparison_type = 'year'
                this.state.date_range = { start_date: this.start_date.el.value, end_date: this.end_date.el.value };
            } else if (dv == 'last-quarter') {
                const lq = today.startOf('quarter').minus({ days: 1 });
                this.start_date.el.value = lq.startOf('quarter').toFormat('yyyy-MM-dd')
                this.end_date.el.value = lq.toFormat('yyyy-MM-dd')
                this.state.date_viewed = ['Q ' + lq.quarter]
                this.state.date_type = 'quarter'; this.state.comparison_type = 'quarter'
                this.state.date_range = { start_date: this.start_date.el.value, end_date: this.end_date.el.value };
            } else if (dv == 'journal') {
                const jid = parseInt(val.target.attributes["data-id"].value, 10);
                if (!val.target.classList.contains("selected-filter")) {
                    this.state.selected_journal_list.push(jid);
                    val.target.classList.add("selected-filter");
                } else {
                    this.state.selected_journal_list =
                        this.state.selected_journal_list.filter(i => i !== jid);
                    val.target.classList.remove("selected-filter");
                }
            } else if (dv == 'account') {
                const accId = parseInt(val.target.attributes["data-id"].value, 10);
                if (!val.target.classList.contains("selected-filter")) {
                    this.state.selected_analytic.push(accId);
                    const rec = this.state.accounts.find(a => a.id === accId);
                    if (rec) this.state.selected_analytic_account_rec.push(rec);
                    val.target.classList.add("selected-filter");
                } else {
                    this.state.selected_analytic =
                        this.state.selected_analytic.filter(id => id !== accId);
                    this.state.selected_analytic_account_rec =
                        this.state.selected_analytic_account_rec.filter(r => r.id !== accId);
                    val.target.classList.remove("selected-filter");
                }
            } else if (dv === 'draft') {
                if (val.target.classList.contains("selected-filter")) {
                    const { cash, ...rest } = this.state.method;
                    this.state.method = rest;
                    val.target.classList.remove("selected-filter");
                } else {
                    this.state.method = { ...this.state.method, 'cash': true };
                    val.target.classList.add("selected-filter");
                }
            }
        }

        if (this.state.apply_comparison == true) {
            if (this.state.comparison_type == 'year') {
                this.state.date_viewed = []
                let cur_year, month;
                if (this.start_date.el.value) {
                    cur_year = new Date(this.start_date.el.value).getFullYear();
                    month = new Date(this.start_date.el.value).getMonth();
                } else {
                    cur_year = new Date(today).getFullYear();
                    month = new Date(today).getMonth();
                }
                this.state.comparison_number = this.period_year.el.value
                for (let i = this.state.comparison_number; i >= 0; i--) {
                    this.state.date_viewed.push(monthNamesShort[month] + ' ' + (cur_year - i));
                }
            } else if (this.state.comparison_type == 'month' || this.state.comparison_type == 'quarter') {
                this.state.date_viewed = []
                this.state.comparison_number = this.period.el.value
            }
        }

        this.state.data = await this.orm.call(
            "account.period.balance", "get_filter_values",
            [this.start_date.el.value, this.end_date.el.value,
             this.state.comparison_number, this.state.comparison_type,
             this.state.selected_journal_list, this.state.selected_analytic,
             this.state.options, this.state.method]);

        var date_viewed = []
        $.each(this.state.data, function (index, value) {
            if (index == 'journal_ids') this.state.journals = value
            if (value.dynamic_date_num) {
                $.each(value.dynamic_date_num, function (index, value) {
                    if (!date_viewed.includes(value)) date_viewed.push(value)
                })
            }
        })
        if (date_viewed.length !== 0) this.state.date_viewed = date_viewed.reverse()
    }

    onPeriodChange(ev)      { this.period_year.el.value = ev.target.value }
    onPeriodYearChange(ev)  { this.period.el.value = ev.target.value }

    isGroupCollapsed(g)          { return !!(this.state.collapsed_groups || {})[g]; }
    toggleGroup(g)               {
        const c = this.state.collapsed_groups || {};
        this.state.collapsed_groups = { ...c, [g]: !c[g] };
    }
    isInternalGroupCollapsed(g)  { return !!(this.state.collapsed_internal_groups || {})[g]; }
    toggleInternalGroup(g)       {
        const c = this.state.collapsed_internal_groups || {};
        this.state.collapsed_internal_groups = { ...c, [g]: !c[g] };
    }

    groupSumByKey(data, groupLabel, key) {
        return (data || [])
            .filter(r => (r.group_label || 'Other') === groupLabel)
            .reduce((a, i) => a + (i[key] || 0), 0);
    }
    internalGroupSumByKey(data, internalGroup, key) {
        return (data || [])
            .filter(r => (r.internal_group || 'Other') === internalGroup)
            .reduce((a, i) => a + (i[key] || 0), 0);
    }
    sumByKey(data, key) {
        return data.reduce((acc, item) => acc + (item[key] || 0), 0);
    }

    applyComparisonPeriod(ev) {
        if (!this.start_date.el?.value || !this.end_date.el?.value) {
            this.env.services.notification.add("Please pick a date range first.", { type: "warning" });
            return;
        }
        this.state.apply_comparison = true;
        this.state.comparison_type = this.state.date_type;
        this.applyFilter(null, ev);
    }
    applyComparisonYear(ev) {
        this.state.apply_comparison = true;
        this.state.comparison_type = 'year';
        this.applyFilter(null, ev);
    }
    async applyComparison(ev) {
        this.state.apply_comparison = false;
        this.state.comparison_type = null;
        this.state.comparison_number = null;
        const lastIndex = this.state.date_viewed.length - 1;
        this.state.date_viewed.splice(0, lastIndex);
        this.applyFilter(null, ev);
    }

    get comparison_number_range() {
        const range = [];
        for (let i = 1; i <= this.state.comparison_number; i++) range.push(i);
        return range;
    }

    async printPdf(ev) {
        ev.preventDefault();
        const self = this;
        const action_title = self.props.action.display_name;
        let comparison_number_range = self.comparison_number_range;
        let data_viewed = self.state.date_viewed;
        if (self.state.apply_comparison && self.comparison_number_range.length > 10) {
            comparison_number_range = self.comparison_number_range.slice(-10);
            data_viewed = self.state.date_viewed.slice(-11);
        }
        return self.action.doAction({
            'type': 'ir.actions.report',
            'report_type': 'qweb-pdf',
            'report_name': 'dynamic_accounts_report.period_balance',
            'report_file': 'dynamic_accounts_report.period_balance',
            'data': {
                'data': self.state.data,
                'date_viewed': data_viewed,
                'filters': this.filter(),
                'apply_comparison': self.state.apply_comparison,
                'comparison_number_range': comparison_number_range,
                'title': action_title,
                'report_name': self.props.action.display_name
            },
            'display_name': self.props.action.display_name,
        });
    }

    filter() {
        const self = this;
        let filters = {
            'journal': Object.values(self.state.selected_journal_list),
            'account': self.state.selected_analytic_account_rec,
            'options': self.state.options,
            'comparison_type': self.state.comparison_type,
            'comparison_number_range': self.state.comparison_number,
            'start_date': self.start_date.el.value,
            'end_date': self.end_date.el.value,
        };
        return filters
    }

    async print_xlsx() {
        const self = this;
        const action_title = self.props.action.display_name;
        const datas = {
            'data': self.state.data,
            'date_viewed': self.state.date_viewed,
            'filters': this.filter(),
            'apply_comparison': self.state.apply_comparison,
            'comparison_number_range': self.comparison_number_range,
            'title': action_title,
            'report_name': self.props.action.display_name
        };
        const action = {
            'data': {
                'model': 'account.period.balance',
                'data': JSON.stringify(datas),
                'output_format': 'xlsx',
                'report_action': self.props.action.xml_id,
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

    formatAmount(value) {
        const num = Number(value || 0);
        return Math.round(num).toLocaleString('en-US');
    }

    async show_gl(ev) {
        const accountName = ev.currentTarget.attributes["data-account-name"]
            ? ev.currentTarget.attributes["data-account-name"].value : null;
        return this.action.doAction({
            type: 'ir.actions.client',
            name: 'General Ledger',
            tag: 'gen_l',
            params: {
                default_title: accountName ? `General Ledger - ${accountName}` : 'General Ledger',
                default_date_range: {
                    start_date: this.start_date.el.value,
                    end_date: this.end_date.el.value,
                },
                default_account_names: accountName ? [accountName] : [],
                default_journal_ids: this.state.selected_journal_list || [],
                default_options: this.state.options || {},
                default_method: this.state.method || { accrual: true },
            },
        });
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const day = date.getDate().toString().padStart(2, '0');
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const year = date.getFullYear();
        return `${day}/${month}/${year}`;
    }

    gotoJournalItem(ev) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: 'account.move.line',
            name: "Journal Items",
            views: [[false, "list"]],
            domain: [["account_id", "=", parseInt(ev.target.attributes["data-id"].value, 10)]],
            context: { group_by: ["account_id"] },
            target: "current",
        });
    }
}
PeriodBalance.template = 'prd_b_template_new';
actionRegistry.add("prd_b", PeriodBalance);