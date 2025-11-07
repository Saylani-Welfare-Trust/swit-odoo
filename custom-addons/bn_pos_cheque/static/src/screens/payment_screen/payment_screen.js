/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const currentOrder = this.currentOrder;
        const pos_cheque_order_id = this.pos.pos_cheque_order_id;

        console.log(currentOrder);
        console.log(pos_cheque_order_id);

        if (currentOrder && pos_cheque_order_id) {
            const data = await this.env.services.orm.call('pos.order', 'settle_cheque_order', [this.pos.pos_session.id, pos_cheque_order_id]);


            if (data.status == "error") {
                this.env.services.notification.add(
                    data.body,
                    { type: 'danger' }
                );
            } else if (condition) {
                this.env.services.notification.add(
                    data.body,
                    { type: 'success' }
                );
            } else {
                this.env.services.notification.add(
                    "Unknown status",
                    { type: 'warning' }
                );
            }
        }

        super.validateOrder(isForceValidate);
    }
});