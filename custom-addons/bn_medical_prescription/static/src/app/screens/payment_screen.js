/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConnectionLostError, RPCError } from "@web/core/network/rpc_service";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        if (order?.medical_prescription_id) {
            try {
                // billed meanwhile at another counter, or cancelled by the prescription desk?
                await this.env.services.orm.silent.call("pos.session", "pos_check_medical_prescription", [
                    [this.pos.pos_session.id],
                    order.medical_prescription_id,
                    order.get_partner()?.id || false,
                ]);
            } catch (error) {
                // offline, the order is billed when it syncs
                if (!(error instanceof ConnectionLostError)) {
                    await this.popup.add(ErrorPopup, {
                        title: _t("Prescription can't be billed"),
                        body: error instanceof RPCError ? error.data.message : String(error),
                    });
                    return;
                }
            }
        }
        return super.validateOrder(...arguments);
    },
});
