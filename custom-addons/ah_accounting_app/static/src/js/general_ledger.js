/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { useRef, useState } from "@odoo/owl";
import {GeneralLedger} from "@dynamic_accounts_report/js/general_ledger";

patch(GeneralLedger.prototype, {
     setup() {
        super.setup(...arguments);
        this.state.analytic_plans = null;
        this.state.selected_analytic_plan_list = [];
     },

    async load_data() {
        let account_list = []
        let account_totals = ''
        let totalDebitSum = 0;
        let totalCreditSum = 0;
        let currency;
        var self = this;
        var action_title = self.props.action.display_name;
        try {
            var self = this;
            console.log(this.state.selected_analytic_plan_list, 'selected_analytic_plan_list')
            self.state.account_data = await self.orm.call("account.general.ledger", "view_report", [[this.wizard_id], action_title, this.state.selected_analytic_plan_list]);
            $.each(self.state.account_data, function (index, value) {
                if (index !== 'account_totals' && index !== 'journal_ids' && index !== 'analytic_ids' && index !== 'analytic_plan_ids') {
                    account_list.push(index)
                }
                else if (index == 'journal_ids') {
                    self.state.journals = value
                }
                else if (index == 'analytic_plan_ids') {
                    self.state.analytic_plans = value
                }
                else if (index == 'analytic_ids') {
                    self.state.analytics = value
                }
                else {
                    account_totals = value
                    Object.values(account_totals).forEach(account_list => {
                        currency = account_list.currency_id
                        totalDebitSum += account_list.total_debit || 0;
                        totalCreditSum += account_list.total_credit || 0;
                    });
                }
            })
            self.state.account = account_list
            self.state.account_list = account_list
            self.state.account_data_list = self.state.account_data
            self.state.account_total_list = account_totals
            self.state.account_total = account_totals
            self.state.currency = currency
            self.state.total_debit = totalDebitSum.toFixed(2)
            self.state.total_credit = totalCreditSum.toFixed(2)
            self.state.title = action_title
        }
        catch (el) {
            window.location.href;
        }
    },

    async applyAnalyticPlan(val){
        self = this;

        if (val.target.attributes["data-value"].value == 'analyticplan') {
            if (!val.target.classList.contains("selected-filter")) {
                this.state.selected_analytic_plan_list.push(parseInt(val.target.attributes["data-id"].value, 10))
                val.target.classList.add("selected-filter");
            } else {
                const updatedList = this.state.selected_analytic_plan_list.filter(item => item !== parseInt(val.target.attributes["data-id"].value, 10));
                this.state.selected_analytic_plan_list = updatedList
                val.target.classList.remove("selected-filter");
            }
        }
        self.initial_render = false;
        self.load_data(self.initial_render);
    },

    async applyFilter(val, ev, is_delete = false) {
        let account_list = []
        let account_totals = ''
        let totalDebitSum = 0;
        let totalCreditSum = 0;
        this.state.account = null
        this.state.account_data = null
        this.state.account_total = null
        this.state.filter_applied = true;
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
            else if (val.target.attributes["data-value"].value == 'analyticplan') {
                if (!val.target.classList.contains("selected-filter")) {
                    this.state.selected_analytic_plan_list.push(parseInt(val.target.attributes["data-id"].value, 10))
                    val.target.classList.add("selected-filter");
                } else {
                    const updatedList = this.state.selected_analytic_plan_list.filter(item => item !== parseInt(val.target.attributes["data-id"].value, 10));
                    this.state.selected_analytic_plan_list = updatedList
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
            }else if (val.target.attributes["data-value"].value === 'cash-basis') {
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
        let filtered_data = await this.orm.call("account.general.ledger", "get_filter_values", [this.state.selected_journal_list, this.state.date_range, this.state.options, this.state.selected_analytic_list,this.state.method, this.state.selected_analytic_plan_list]);
        $.each(filtered_data, function (index, value) {
            if (index !== 'account_totals' && index !== 'journal_ids' && index !== 'analytic_ids' && index !== 'analytic_plan_ids') {
                account_list.push(index)
            }
            else {
                account_totals = value
                Object.values(account_totals).forEach(account_list => {
                        totalDebitSum += account_list.total_debit || 0;
                        totalCreditSum += account_list.total_credit || 0;
                    });
            }
        })
        this.state.account = account_list
        this.state.account_data = filtered_data
        this.state.account_total = account_totals
        this.state.total_debit = totalDebitSum.toFixed(2)
        this.state.total_credit = totalCreditSum.toFixed(2)
        if ($(this.unfoldButton.el.classList).find("selected-filter")) {
            this.unfoldButton.el.classList.remove("selected-filter")
        }
    }


});