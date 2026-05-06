/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        // Get WhatsApp number BEFORE validation
        const order = this.currentOrder;
        const partner = order ? order.partner : null;
        const whatsappNumber = partner ? (partner.whatsapp || partner.mobile) : null;

        // ✅ Store reference BEFORE component is destroyed
        const orderRef = order;

        // Call original method
        const result = await super.validateOrder(...arguments);

        if (whatsappNumber) {
            setTimeout(async () => {
                // ⚠️ DO NOT use this.currentOrder here
                const orderId = orderRef ? orderRef.server_id : null;

                if (orderId) {
                    fetch('/web/dataset/call_kw', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            jsonrpc: '2.0',
                            method: 'call',
                            params: {
                                model: 'pos.order',
                                method: 'sms_or_whatsapp_send_receipt',
                                args: [orderId],
                                kwargs: {},
                            },
                            id: Date.now(),
                        }),
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.result?.status === 'success') {
                            console.log(data.result?.message);
                        }
                    })
                    .catch(error => console.error("Error:", error));
                } else {
                    console.log("No Order ID found");
                }
            }, 5000);
        }

        return result;
    },
});