/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const currentOrder = this.currentOrder;

        console.log('New Rasie Amount Button Clicked');
        console.log(currentOrder);

        // 🔹 First call your custom method
        // const data = await this.orm.call('key.issuance', "set_donation_amount", [donationBoxData]);

        // if (data.status === 'error') {
        //     this.popup.add(ErrorPopup, {
        //         title: _t("Error"),
        //         body: data.body,
        //     });
        //     return;
        // }

        // if (data.status === 'success') {
        //     currentOrder.set_source_document(data.name)

        //     this.env.services.notification.add(_t("Amount Recorded Successfully"), { type: "success" });
            
        //     return this.report.doAction("point_of_sale.sale_details_report", [this.pos.pos_session.id]);
        // }

        // Continue with normal POS flow
        super.validateOrder(isForceValidate);
    }
})