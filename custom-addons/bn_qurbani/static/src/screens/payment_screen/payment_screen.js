/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        // Continue with normal POS flow
        super.validateOrder(isForceValidate);
        
        const currentOrder = this.currentOrder;

        let hasValidProduct = false;

        // -------------------------
        // ✅ Check Order Lines
        // -------------------------
        for (let line of currentOrder.get_orderlines()) {
            const product = line.product;

            const isLivestock = product.is_livestock;
            const isService = product.type === 'service';
            const isQurbaniCategory =
                product.categ &&
                product.categ.name &&
                product.categ.name.toLowerCase().includes('qurbani');

            if (isLivestock && isService && isQurbaniCategory) {
                hasValidProduct = true;
                break;
            }
        }

        if (!hasValidProduct) {
            // 🔹 First call your custom method
            const data = await this.orm.call('qurbani.order', "select_order", [currentOrder.name]);

            if (data.status === 'error') {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: data.body,
                });
                return;
            }

            if (data.status === 'success') {
                currentOrder.set_source_document(data.name)

                this.env.services.notification.add(_t("Amount Recorded Successfully"), { type: "success" });
                
                return this.report.doAction("bn_qurbani.qurbani_token_report", [data.id]);
            }
        }
    }
})