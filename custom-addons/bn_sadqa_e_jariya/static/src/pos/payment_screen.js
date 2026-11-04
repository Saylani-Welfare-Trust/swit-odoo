/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreen.prototype, {
    /**
     * HOD lines the cashier deleted from the order are not paid, they are cancelled
     */
    _dropDeletedSadqaJariyaHodLines(order, data) {
        const keptIds = order.get_orderlines().map((line) => line.sadqa_jariya_hod_line_id).filter(Boolean);
        const deletedIds = data.line_ids.filter((line) => line.is_hod && !keptIds.includes(line.id)).map((line) => line.id);
        data.line_ids = data.line_ids.filter((line) => !deletedIds.includes(line.id));
        return deletedIds;
    },

    /**
     * Runs once the payment is valid, before the order is saved: the lines are paid / returned here
     */
    async _finalizeValidation() {
        const order = this.currentOrder;
        const data = order.extra_data?.sadqa_jariya;
        const returnData = order.extra_data?.sadqa_jariya_return;
        try {
            if (data && data.disbursement_status === "pending") {
                const removedHodIds = data.is_recurring ? [] : this._dropDeletedSadqaJariyaHodLines(order, data);
                const ids = data.line_ids.map((line) => line.id);
                if (ids.length) {
                    await this.env.services.orm.call(data.line_model, "action_disbursed", [ids]);
                }
                if (removedHodIds.length) {
                    await this.env.services.orm.call("sadqa.jariya.line", "action_cancel_from_pos", [removedHodIds]);
                }
                data.disbursement_status = "completed";
                data.total_disbursed_amount = data.line_ids.reduce((sum, line) => sum + (line.amount || 0), 0);
                order.set_source_document(data.record_number);
                this.env.services.notification.add(
                    _t("Sadqa e Jariya %s disbursement completed. Amount: %s", data.record_number, data.total_disbursed_amount),
                    { type: "success" }
                );
            }
            if (returnData && returnData.status === "pending") {
                for (const id of returnData.line_ids) {
                    await this.env.services.orm.call(returnData.line_model, "action_return_to_pos", [[id]]);
                }
                returnData.status = "completed";
                order.set_source_document(returnData.record_number);
                this.env.services.notification.add(
                    _t("Sadqa e Jariya return processed: %s", returnData.record_number),
                    { type: "success" }
                );
            }
        } catch (error) {
            console.error("Sadqa e Jariya Error:", error);
            await this.popup.add(ErrorPopup, {
                title: _t("Sadqa e Jariya Payment Blocked"),
                body: error.data?.message || error.message || _t("This Sadqa e Jariya payment could not be processed."),
            });
            return;
        }
        return super._finalizeValidation(...arguments);
    },
});
