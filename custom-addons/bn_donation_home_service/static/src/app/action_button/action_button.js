/** @odoo-module */

import { ActionButton } from "@bn_pos_custom_action/app/action_button/action_button";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionButton.prototype, {
    async setup() {
        await super.setup(...arguments);

        this.pos._donationHomeService = await this.env.services.user.hasGroup('bn_donation_home_service.donation_home_service_pos_action_group');
    }
});