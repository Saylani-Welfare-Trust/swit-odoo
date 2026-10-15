/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class TreasuryDashboard extends Component {
    static template = "treasury_dashboard.Dashboard";

    setup() {
        this.actionService = useService("action");
        
        // State now only holds the 3 custom models
        this.state = useState({
            cheques: { count: 0, total_amount: 0, states: {} },
            deposits: { count: 0, total_amount: 0, states: {} },
            transfers: { count: 0, total_amount: 0, states: {} },
        });

        onWillStart(async () => {
            const data = await this.env.services.rpc("/treasury/dashboard/data", {});
            this.state.cheques = data.cheques;
            this.state.deposits = data.deposits;
            this.state.transfers = data.transfers;
        });
    }

    // Generic method to open custom model list views
    openCustomModel(modelName) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: modelName,
            views: [[false, 'list'], [false, 'form']],
            target: 'current'
        });
    }

    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
    }
}

registry.category("actions").add("treasury_dashboard", TreasuryDashboard);