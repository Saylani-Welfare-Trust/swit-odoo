/** @odoo-module */

import { onWillStart } from "@odoo/owl";
import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(ActionScreen.prototype, {
    setup() {
        super.setup(...arguments);
        onWillStart(async () => {
            this.sadqaJariyaAccess = await this.env.services.user.hasGroup(
                "bn_sadqa_e_jariya.group_sadqa_jariya_pos_action"
            );
        });
    },

    clickRecordSJ() {
        this.notification.add(
            _t("Sadqa e Jariya disbursements are processed through Bank, not POS."),
            { type: "warning" }
        );
    },
});
