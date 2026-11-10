/** @odoo-module */

import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(ReceivingPopup.prototype, {
    async confirm() {
        if (this.props.action_type === "sj" && this.state.record_number) {
            this.notification.add(
                _t("Sadqa e Jariya disbursements are processed through Bank, not POS."),
                { type: "warning" }
            );
            this.cancel();
            return;
        }
        return super.confirm(...arguments);
    },
});
