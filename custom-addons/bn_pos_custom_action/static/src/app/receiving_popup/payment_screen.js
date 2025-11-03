/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { TextAreaPopup } from "@point_of_sale/app/utils/input_popups/textarea_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        console.log("🔵 [Medical Equipment] validateOrder method STARTED");
        
        // Store reference to current order before any popups
        const currentOrder = this.currentOrder;
        
        // Check if this order has medical equipment data BEFORE any popups
        if (currentOrder && currentOrder.medical_equipment_data) {
            console.log("🔵 [Medical Equipment] Medical equipment data found:", currentOrder.medical_equipment_data);
        } else {
            console.log("🟡 [Medical Equipment] No medical equipment data found");
        }

       
        // // Call original validateOrder first
        // console.log("🔵 [Medical Equipment] Calling original validateOrder...");
        // await super.validateOrder(...arguments);
        
        // After original validateOrder completes, update medical equipment state
        if (currentOrder && currentOrder.medical_equipment_data) {
            try {
                console.log("🔵 [Medical Equipment] Updating medical equipment state...");
                
                // Update medical equipment state to 'payment_received'
                const result = await this.env.services.orm.call(
                    'medical.equipment',
                    'write',
                    [[currentOrder.medical_equipment_data.record_id]],
                    { state: 'payment_received' }
                );
                
                console.log("✅ [Medical Equipment] State updated successfully:", result);
                console.log(`✅ Medical equipment ${currentOrder.medical_equipment_data.record_number} state updated to payment_received`);
                
                // Show notification
                this.env.services.notification.add(
                    `Medical equipment ${currentOrder.medical_equipment_data.record_number} marked as paid`,
                    { type: 'success' }
                );
                console.log("🔵 [Medical Equipment] Calling original validateOrder...");
                await super.validateOrder(...arguments);
                
            } catch (error) {
                console.error("❌ [Medical Equipment] Error updating state:", error);
                this.env.services.notification.add(
                    "Failed to update equipment status",
                    { type: 'danger' }
                );
            }
        }
    },
  
});