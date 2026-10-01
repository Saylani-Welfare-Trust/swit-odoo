/** @odoo-module */

import { ActionButton } from "@bn_pos_custom_action/app/action_button/action_button";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionButton.prototype, {
    async setup() {
        await super.setup(...arguments);

        this.pos._donationBox = await this.env.services.user.hasGroup('bn_donation_box.donation_box_pos_action_group');
    }
});