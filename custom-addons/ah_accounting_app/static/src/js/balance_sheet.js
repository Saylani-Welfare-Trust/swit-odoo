/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import {BalanceSheet} from "@dynamic_accounts_report/js/balance_sheet";

patch(BalanceSheet.prototype, {
     setup() {
        super.setup(...arguments);
        this.analytic_plan_ids = new Set();
     },


    async load_data() {
        var self = this;
        var action_title = self.props.action.display_name;
        try {
            var self = this;
            let selected_analytic_plan_ids = await self.orm.call("dynamic.balance.sheet.report", "get_analytic_plan_ids", [this.wizard_id]);
            let data = await self.orm.call("dynamic.balance.sheet.report", "view_report", [this.wizard_id,this.state.comparison,this.state.comparison_type, selected_analytic_plan_ids]);
            self.state.data = data[0]
            self.state.datas = data[2]
            self.state.filter_data = data[1]
            self.state.title = action_title
        }
        catch (el) {
            window.location.href
        }
    },

    async apply_analytic_plans(ev) {
        self = this;
        if (ev.target.classList.contains("selected-filter")) {
            ev.target.classList.remove('selected-filter');
        } else {
            ev.target.classList.add('selected-filter');
        }
        this.filter = {
            'analytic_plan_ids': ev.target.querySelector('span').textContent,
        };
        let res = await self.orm.call("dynamic.balance.sheet.report", "filter", [this.wizard_id, this.filter]);
        ev.delegateTarget.querySelector('.analytic_p').innerHTML = res[0].analytic_plan_ids;
        self.initial_render = false;
        self.load_data(self.initial_render);
     },

     async apply_analytic_sub_plans(ev) {
        self = this;
        if (ev.target.classList.contains("selected-filter")) {
            ev.target.classList.remove('selected-filter');
        } else {
            ev.target.classList.add('selected-filter');
        }
        this.filter = {
            'analytic_sub_plan_ids': ev.target.querySelector('span').textContent,
        };
        let res = await self.orm.call("dynamic.balance.sheet.report", "filter", [this.wizard_id, this.filter]);
        ev.delegateTarget.querySelector('.analytic_sp').innerHTML = res[0].analytic_sub_plan_ids;
        self.initial_render = false;
        self.load_data(self.initial_render);
     }

});