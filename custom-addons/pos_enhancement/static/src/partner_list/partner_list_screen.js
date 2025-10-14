/** @odoo-module */

import { PartnerListScreen } from "@point_of_sale/app/screens/partner_list/partner_list";
import { patch } from "@web/core/utils/patch";
import { onWillStart } from "@odoo/owl";

patch(PartnerListScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.is_registration_user = false

        onWillStart(async () => {
            this.is_registration_user = await this.pos.env.services.user.hasGroup("pos_enhancement.group_pos_registration_user")
        })
    },

});
