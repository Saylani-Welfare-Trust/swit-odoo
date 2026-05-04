/** @odoo-module **/


import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

const originalValidateOrder = PaymentScreen.prototype.validateOrder;

PaymentScreen.prototype.validateOrder = async function(isForceValidate) {
    console.log("🔵 VALIDATE ORDER HIT! 🔵");
    
    // Get WhatsApp number BEFORE validation
    const order = this.currentOrder;
    const partner = order ? order.partner : null;
    const whatsappNumber = partner ? (partner.whatsapp || partner.mobile) : null;
    
    console.log("WhatsApp:", whatsappNumber);
    
    // Call original validate
    const result = await originalValidateOrder.call(this, isForceValidate);
    
    if (whatsappNumber) {
        // Wait 3 seconds for order to be saved in database
        setTimeout(async () => {
            // Get order ID from current order (after validation)
            const orderId = this.currentOrder ? this.currentOrder.server_id : null;
            
            console.log("Order ID:", orderId);
            
            if (orderId) {
                console.log("Sending WhatsApp for Order ID:", orderId);
                
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
                    })
                })
                .then(response => response.json())
                .then(data => {
                    console.log("Response:", data);
                    if (data.result?.status === 'success') {
                        console.log(data.result?.message);
                    }
                })
                .catch(error => console.error("Error:", error));
            } else {
                console.log("No Order ID found");
            }
        }, 5000);  // 5 seconds delay
    }
    
    return result;
};

console.log("===== JS OVERRIDE APPLIED =====");