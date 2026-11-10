/** @odoo-module */

import { ActionButton } from "@bn_pos_custom_action/app/action_button/action_button";
import { patch } from "@web/core/utils/patch";


patch(ActionButton.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.pos._microFinance = await this.env.services.user.hasGroup('bn_microfinance.microfinance_pos_action_group');
    },
});
