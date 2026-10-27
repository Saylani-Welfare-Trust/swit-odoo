/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

// Donation Home Service paid at the POS: marked Paid once the order is saved.
patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const dhsData = order && order.extra_data && order.extra_data.dhs;
        if (!dhsData || !dhsData.dhs_id) {
            return super.validateOrder(...arguments);
        }
        order.set_source_document(dhsData.record_number);
        const result = await super.validateOrder(...arguments);
        if (!order.finalized) {
            return result;
        }
        try {
            const [record] = await this.env.services.orm.searchRead(
                'donation.home.service', [['id', '=', dhsData.dhs_id]], ['state'], { limit: 1 });
            if (record && record.state !== 'paid') {
                await this.env.services.orm.write('donation.home.service', [dhsData.dhs_id], { state: 'paid' });
                this.env.services.notification.add(
                    `Donation Home Service ${dhsData.record_number} payment processed`,
                    { type: 'success' }
                );
            }
        } catch (error) {
            console.error("[Donation Home Service] Error updating state:", error);
            this.env.services.notification.add(
                `Order ${order.name} is saved, but Donation Home Service ${dhsData.record_number} was not marked paid. Please inform the team.`,
                { type: 'danger', sticky: true }
            );
        }
        return result;
    },
});
