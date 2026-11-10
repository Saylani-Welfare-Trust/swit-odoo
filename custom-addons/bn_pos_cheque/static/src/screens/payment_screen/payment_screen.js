/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    // Settling a bounced cheque gives it back to the donor: done only once
    // the return order is saved, so a cancelled payment leaves it open.
    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const pos_cheque_order_id = order && order.get_pos_cheque_order_id();
        const result = await super.validateOrder(...arguments);
        if (!pos_cheque_order_id || !order.finalized) {
            return result;
        }
        try {
            const data = await this.env.services.orm.call('pos.order', 'settle_cheque_order', [pos_cheque_order_id]);
            this.env.services.notification.add(data.body, { type: data.status == "success" ? 'success' : 'danger' });
        } catch (error) {
            this.env.services.notification.add(
                `Order ${order.name} is saved, but the cheque was not marked settled. Please inform treasury.`,
                { type: 'danger', sticky: true }
            );
        }
        return result;
    }
});
