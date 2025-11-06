


/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

console.log("🟢 Medical Equipment Payment Screen Patch - LOADED");

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        console.log("🔵 [Medical Equipment] validateOrder method STARTED");
        console.log("🔵 Current Order:", this.currentOrder);
        console.log("🔵 Order extra_data:", this.currentOrder?.extra_data);
        
        const currentOrder = this.currentOrder;
        
        // Only process medical equipment if order has extra_data with medical_equipment
        if (currentOrder && currentOrder.extra_data && currentOrder.extra_data.medical_equipment) {
            console.log("🔵 [Medical Equipment] Medical equipment data found:", currentOrder.extra_data.medical_equipment);
            
            try {
                const medicalData = currentOrder.extra_data.medical_equipment;
                const equipmentId = medicalData.equipment_id;
                console.log("🔵 [Medical Equipment] Equipment ID to update:", equipmentId);
                
                if (equipmentId) {
                    // First, get the current state of the medical equipment record
                    const equipmentRecord = await this.env.services.orm.searchRead(
                        'medical.equipment',
                        [['id', '=', equipmentId]],
                        ['name', 'state'],
                        { limit: 1 }
                    );
                    
                    if (equipmentRecord && equipmentRecord.length > 0) {
                        const currentState = equipmentRecord[0].state;
                        console.log("🔵 [Medical Equipment] Current equipment state:", currentState);
                        
                        let newState;
                        
                        // Condition 1: If state is 'draft', update to 'payment'
                        if (currentState === 'draft') {
                            newState = 'payment_received';
                            console.log("🔄 [Medical Equipment] Updating from draft to payment");
                        }
                        // Condition 2: If state is 'return', update to 'payment_return'
                        else if (currentState === 'return') {
                            newState = 'payment_return';
                            console.log("🔄 [Medical Equipment] Updating from return to payment_return");
                        }
                        // For other states, don't update or use default
                        else {
                            console.log("🟡 [Medical Equipment] No state update needed for current state:", currentState);
                            newState = currentState; // Keep current state
                        }
                        
                        // Only update if state changed
                        if (newState && newState !== currentState) {
                            const result = await this.env.services.orm.write(
                                'medical.equipment',
                                [equipmentId],
                                { state: newState }
                            );
                            
                            console.log("✅ [Medical Equipment] State updated successfully:", result);
                            
                            // Show appropriate notification based on state change
                            if (currentState === 'draft') {
                                this.env.services.notification.add(
                                    `Medical equipment ${medicalData.record_number} marked as paid`,
                                    { type: 'success' }
                                );
                            } else if (currentState === 'return') {
                                this.env.services.notification.add(
                                    `Medical equipment ${medicalData.record_number} return payment processed`,
                                    { type: 'success' }
                                );
                            }
                        } else {
                            console.log("🟡 [Medical Equipment] No state change required");
                        }
                        
                    } else {
                        console.error("❌ [Medical Equipment] Equipment record not found");
                    }
                    
                } else {
                    console.error("❌ [Medical Equipment] No equipment ID found");
                }
                
            } catch (error) {
                console.error("❌ [Medical Equipment] Error updating state:", error);
                console.error("❌ Full error details:", JSON.stringify(error, null, 2));
                this.env.services.notification.add(
                    "Note: Equipment status not updated, but order will proceed",
                    { type: 'warning' }
                );
            }
        } else {
            console.log("🟡 [Medical Equipment] No medical equipment data found in order - using normal POS flow");
        }

        console.log("🔵 [Medical Equipment] Calling original validateOrder...");
        // Continue with normal POS flow
        return await super.validateOrder(isForceValidate);
    }
});