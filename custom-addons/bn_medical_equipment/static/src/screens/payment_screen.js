/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

// Medical equipment security deposits, payments and refunds at the POS
// (moved from bn_pos_custom_action).
patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const currentOrder = this.currentOrder;

        // Only process medical equipment if order has extra_data with medical_equipment
        if (currentOrder && currentOrder.extra_data && currentOrder.extra_data.medical_equipment) {
            const medicalData = currentOrder.extra_data.medical_equipment;
            const equipmentId = medicalData.equipment_id;
            const medical_equipment_request_no = medicalData.medical_equipment_request_no;
            const securityDepositId = medicalData.security_deposit_id;
            
            if (equipmentId) {
                // First, get the current state of the medical equipment record
                
                const equipmentRecord = await this.env.services.orm.searchRead(
                    'medical.equipment',
                    [['id', '=', equipmentId]],
                    ['name', 'state', 'medical_equipment_line_ids','remaining_amount'],
                    { limit: 1 }
                );
            
                if (equipmentRecord && equipmentRecord.length > 0) {
                    const currentState = equipmentRecord[0].state;
                    // console.log(`🔍 Current state of equipment ${medicalData.record_number}: ${currentState}`);
                    let newState;
                    if (currentState === 'donate' ) {
                        // console.warn(`⚠️ Remaining amount for donated equipment. Setting remaining_amount to 0.`);
                        const result = await this.env.services.orm.write(
                            'medical.equipment',
                            [equipmentId],
                            { remaining_amount: 0 }
                        );   
                    }
                    // Condition 1: If state is 'draft', update to 'payment'
                    if (currentState === 'sd_received') {
                        // Check for negative quantities
                        const hasNegativeQty = currentOrder
                            .get_orderlines()
                            .some((line) => line.get_quantity() < 0);

                        if (hasNegativeQty) {
                            await this.popup.add(ErrorPopup, {
                                title: _t("Invalid Quantity"),
                                body: _t("You cannot process an order with negative quantities."),
                            });
                            return; // Stop validation
                        }

                        newState = 'payment_received';
                    }
                    // Condition 2: If state is 'refund', update to 'payment_return'
                    else if (currentState === 'refund') {
                        const checkUpdate = await this.processEquipmentLines(equipmentRecord[0], currentOrder);
                    
                        if (checkUpdate) {
                            return super.validateOrder(isForceValidate);
                        }

                        newState = 'payment_return';
                    }
                    // For other states, don't update or use default
                    else {
                        newState = currentState; // Keep current state
                    }
                    
                    // Only update if state changed
                    if (newState && newState !== currentState) {
                        const result = await this.env.services.orm.write(
                            'medical.equipment',
                            [equipmentId],
                            { state: newState }
                        );
                        
                        // Show appropriate notification based on state change
                        if (currentState === 'approved') {
                            currentOrder.set_source_document(medicalData.record_number);

                            this.env.services.notification.add(
                                `Medical equipment ${medicalData.record_number} marked as paid`,
                                { type: 'success' }
                            );
                        } else if (currentState === 'refund') {
                            currentOrder.set_source_document(medicalData.record_number);

                            this.env.services.notification.add(
                                `Medical equipment ${medicalData.record_number} refund payment processed`,
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
                // if (!securityDepositId) {
                const payment_method = currentOrder.paymentlines[0]?.name || 'Cash';

                const payload = {
                    deposit_id: securityDepositId || null,
                    payment_method: payment_method == 'Cash' ? 'cash' : 'cheque',
                    bank_name: currentOrder.bank_name,
                    medical_equipment_request_no: medical_equipment_request_no,
                    cheque_no: currentOrder.cheque_number,
                    cheque_date: currentOrder.cheque_date,
                    state: 'paid',
                }
                console.log("📤 Payload for setting security deposit values:", payload);

                await this.env.services.orm.call(
                    'medical.security.deposit', "set_security_depsoit_values",
                    [payload]
                );
                currentOrder.set_source_document(medicalData.record_number);
                // }
                
                console.log("✅ Security deposit values set successfully");
                // console.error("❌ [Medical Equipment] No equipment ID found");
            }
            
        }

        return super.validateOrder(...arguments);
    },

    /**
     * Process equipment lines and add products to POS order
     */
    async processEquipmentLines(record, selectedOrder) {
        if (!this.hasEquipmentLines(record)) {
            return;
        }

        const equipmentLines = await this.fetchEquipmentLines(record);

        for (const line of equipmentLines) {
            const equipmentLineId = line.id;
            const productId = line.product_id[0];
            const productName = line.product_id[1];
            const equipmentQty = line.quantity || 0;

            const orderLine = selectedOrder.orderlines.find(
                (ol) => ol.product.id === productId
            );

            if (orderLine) {
                const orderQty = orderLine.quantity || 0;
                const absOrderQty = Math.abs(orderQty); // ✅ Treat -3 and 3 as same

                // Detect quantity mismatch
                if (absOrderQty !== equipmentQty) {
                    let newQty = equipmentQty - absOrderQty;

                    // ✅ Prevent negative quantities
                    if (newQty < 0) {
                        newQty = 0;
                        console.warn(`⚠️ Prevented negative qty for ${productName}`);
                    }

                    try {
                        await this.env.services.orm.write(
                            "medical.equipment.line",
                            [equipmentLineId],
                            { quantity: newQty }
                        );

                        this.env.services.notification.add(
                            `${productName} quantity updated: ${equipmentQty} → ${newQty}`,
                            { type: "info" }
                        );
                    } catch (error) {
                        console.error(`❌ Failed to update ${productName}`, error);
                        this.env.services.notification.add(
                            `Error updating quantity for ${productName}`,
                            { type: "warning" }
                        );
                    }

                    return true;
                } else {
                    return false;
                }
            } else {
                console.warn(`⚠️ Product ${productName} not found in POS order`);
            }
        }
    },

    /**
     * Check if equipment has lines
     */
    hasEquipmentLines(record) {
        if (!record.medical_equipment_line_ids || record.medical_equipment_line_ids.length === 0) {
            this.notification.add(
                "No products configured for this equipment",
                { type: 'warning' }
            );
            return false;
        }
        return true;
    },

    /**
     * Fetch equipment lines from database
     */
    async fetchEquipmentLines(record) {
        const equipmentLines = await this.orm.searchRead(
            'medical.equipment.line',
            [['id', 'in', record.medical_equipment_line_ids]],
            ['id', 'product_id', 'quantity'],
            {}
        );
        
        return equipmentLines;
    },
});
