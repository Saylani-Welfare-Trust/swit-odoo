/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const currentOrder = this.currentOrder;
        
        // Only process medical equipment if order has extra_data with medical_equipment
        if (currentOrder && currentOrder.extra_data && currentOrder.extra_data.medical_equipment) {
            const medicalData = currentOrder.extra_data.medical_equipment;
            const equipmentId = medicalData.equipment_id;
            
            if (equipmentId) {
                // First, get the current state of the medical equipment record
                const equipmentRecord = await this.env.services.orm.searchRead(
                    'medical.equipment',
                    [['id', '=', equipmentId]],
                    ['name', 'state', 'medical_equipment_line_ids'],
                    { limit: 1 }
                );
                
                if (equipmentRecord && equipmentRecord.length > 0) {
                    const currentState = equipmentRecord[0].state;
                    
                    let newState;
                    
                    // Condition 1: If state is 'draft', update to 'payment'
                    if (currentState === 'draft') {
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
                    // Condition 2: If state is 'return', update to 'payment_return'
                    else if (currentState === 'return') {
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
        }
        // Only process donation home service if order has extra_data with dhs
        if (currentOrder && currentOrder.extra_data && currentOrder.extra_data.dhs) {
            try {
                const dhsData = currentOrder.extra_data.dhs;
                const dhsId = dhsData.dhs_id;
                
                if (dhsId) {
                    // First, get the current state of the medical equipment record
                    const dhsRecord = await this.env.services.orm.searchRead(
                        'donation.home.service',
                        [['id', '=', dhsId]],
                        ['name', 'state'],
                        { limit: 1 }
                    );
                    
                    if (dhsRecord && dhsRecord.length > 0) {
                        const currentState = dhsRecord[0].state;
                        
                        const newState = 'paid'; // Keep current state
                        
                        // Only update if state changed
                        if (newState && newState !== currentState) {
                            const result = await this.env.services.orm.write(
                                'donation.home.service',
                                [dhsId],
                                { state: newState }
                            );
                            
                            // Show appropriate notification based on state change
                            if (currentState === 'gate_in') {
                                this.env.services.notification.add(
                                    `Donation Home Service ${dhsData.record_number} payment processed`,
                                    { type: 'success' }
                                );
                            }
                        } else {
                            console.log("🟡 [Donation Home Service] No state change required");
                        }
                    } else {
                        console.error("❌ [Donation Home Service] Equipment record not found");
                    }
                } else {
                    console.error("❌ [Donation Home Service] No donation home service ID found");
                }
            } catch (error) {
                console.error("❌ [Donation Home Service] Error updating state:", error);
                this.env.services.notification.add(
                    "Note: Donation Home Service status not updated, but order will proceed",
                    { type: 'warning' }
                );
            }
        }
        // --- MICROFINANCE ---
        if (currentOrder && currentOrder.extra_data && currentOrder.extra_data.microfinance) {
            const mfData = currentOrder.extra_data.microfinance;
            

            if (mfData.security_desposit) {
                const depositID = mfData.security_deposit_id || null;
                const payment_method = currentOrder.paymentlines[0]?.name || 'Cash';
                const partnerId = currentOrder.get_partner()?.id || null;

                

                if (depositID) {
                    // Update existing record
                    await this.env.services.orm.write(
                        'microfinance.installment',
                        [depositID],
                        {
                            payment_method: payment_method == 'Cash' ? 'cash' : 'cheque',
                            bank_name: currentOrder.bank_name,
                            cheque_no: currentOrder.cheque_number,
                            cheque_date: currentOrder.cheque_date,
                            donee_id: partnerId,
                            state: 'paid',
                        }
                    );
                    
                    this.env.services.notification.add(
                        `Deposit Received successfully`,
                        { type: 'success' }
                    );
                } else {
                    // Create new microfinance.installment record if it doesn't exist
                    const microfinanceId = mfData.microfinance_id || null;
                    const amount = mfData.amount || 0;

                    try {
                        const newInstallment = await this.env.services.orm.create(
                            'microfinance.installment',
                            [{
                                payment_type: 'security',
                                payment_method: payment_method == 'Cash' ? 'cash' : 'cheque',
                                bank_name: currentOrder.bank_name || false,
                                cheque_no: currentOrder.cheque_number || false,
                                cheque_date: currentOrder.cheque_date || false,
                                microfinance_id: microfinanceId,
                                donee_id: partnerId,
                                amount: amount,
                                date: new Date().toISOString().split('T')[0],
                                state: 'paid',
                            }]
                        );

                        console.log("🟢 [Microfinance] Created installment:", newInstallment);

                        if (newInstallment) {
                            this.env.services.notification.add(
                                `Security Deposit record created and paid successfully`,
                                { type: 'success' }
                            );
                        }
                    } catch (error) {
                        console.error("❌ [Microfinance] Error creating installment:", error);
                        this.env.services.notification.add(
                            `Error creating security deposit: ${error.message}`,
                            { type: 'danger' }
                        );
                    }
                }
            } else {
                const microfinanceLineIds = mfData.microfinance_line_ids || [];
                
                if (microfinanceLineIds.length > 0) {
                    const payment_method = currentOrder.paymentlines[0]?.name || 'Cash';
                    const partnerId = currentOrder.get_partner()?.id || null;
                    const microfinanceId = mfData.microfinance_id || null;
                    
                    // Get the actual paid amount from the order line (user may have modified it)
                    let actualPaidAmount = 0;
                    const orderLines = currentOrder.get_orderlines();
                    for (const ol of orderLines) {
                        // Find Microfinance Installment product line
                        if (ol.product && ol.product.display_name === 'Microfinance Installment') {
                            actualPaidAmount += ol.get_price_with_tax();
                        }
                    }
                    
                    console.log("🟢 [Microfinance] Actual paid amount from order:", actualPaidAmount);
                    console.log("🟢 [Microfinance] Unpaid lines to process:", microfinanceLineIds);
                    
                    // Distribute payment across installment lines (sorted by due_date - already sorted)
                    let remainingPayment = actualPaidAmount;
                    let processedLines = 0;
                    
                    for (const line of microfinanceLineIds) {
                        if (remainingPayment <= 0) break;
                        
                        const lineRemaining = line.remaining_amount || (line.amount - (line.paid_amount || 0));
                        
                        if (lineRemaining <= 0) continue; // Skip fully paid lines
                        
                        let paymentForThisLine = 0;
                        let newState = 'unpaid';
                        
                        if (remainingPayment >= lineRemaining) {
                            // Full payment for this line
                            paymentForThisLine = lineRemaining;
                            remainingPayment -= lineRemaining;
                            newState = 'paid';
                        } else {
                            // Partial payment for this line
                            paymentForThisLine = remainingPayment;
                            remainingPayment = 0;
                            newState = 'partial';
                        }
                        
                        const newPaidAmount = (line.paid_amount || 0) + paymentForThisLine;
                        
                        await this.env.services.orm.write(
                            'microfinance.line',
                            [line.id],
                            {
                                paid_amount: newPaidAmount,
                                state: newState,
                            }
                        );
                        
                        console.log(`🟢 [Microfinance] Line ${line.id}: paid ${paymentForThisLine}, new total: ${newPaidAmount}, state: ${newState}`);
                        processedLines++;
                    }
                    
                    // Create microfinance.installment record for tracking the installment payment
                    try {
                        const newInstallment = await this.env.services.orm.create(
                            'microfinance.installment',
                            [{
                                payment_type: 'installment',
                                payment_method: payment_method == 'Cash' ? 'cash' : 'cheque',
                                bank_name: currentOrder.bank_name || false,
                                cheque_no: currentOrder.cheque_number || false,
                                cheque_date: currentOrder.cheque_date || false,
                                microfinance_id: microfinanceId,
                                donee_id: partnerId,
                                amount: actualPaidAmount,
                                date: new Date().toISOString().split('T')[0],
                                state: 'paid',
                            }]
                        );
                        
                        console.log("🟢 [Microfinance] Created installment record:", newInstallment);
                    } catch (error) {
                        console.error("❌ [Microfinance] Error creating installment record:", error);
                    }
                    
                    this.env.services.notification.add(
                        `Processed payment of ${actualPaidAmount} across ${processedLines} installment(s)`,
                        { type: 'success' }
                    );
                } else {
                    const microfinanceRecoveryLineIds = mfData.microfinance_recovery_line_ids || [];
                    
                    // Fetch unpaid microfinance lines
                    
                    for (const line of microfinanceRecoveryLineIds) {
                        await this.env.services.orm.write(
                            'microfinance.recovery.line',
                            [line.id],
                            {
                                paid_amount: line.amount,
                                state: 'paid', // optional
                            }
                        );
                    }
                    
                    this.env.services.notification.add(
                        `Processed ${microfinanceLineIds.length} microfinance instalments`,
                        { type: 'success' }
                    );
                }
            }

        }

        // --- WELFARE ---
        if (currentOrder && currentOrder.extra_data && currentOrder.extra_data.welfare) {
            try {
                const wfData = currentOrder.extra_data.welfare;
                const welfareId = wfData.welfare_id;
                const isRecurring = wfData.is_recurring;

                if (welfareId) {
                    if (!isRecurring) {
                        // One-time disbursement: Update welfare.state to 'disbursed'
                        await this.env.services.orm.write(
                            'welfare',
                            [welfareId],
                            { state: 'disbursed' }
                        );

                        this.env.services.notification.add(
                            `Welfare ${wfData.record_number} one-time disbursement completed`,
                            { type: 'success' }
                        );
                    } else {
                        // Recurring disbursement: Update recurring lines to 'disbursed'
                        const recurringLineIds = wfData.recurring_line_ids || [];
                        
                        if (recurringLineIds.length > 0) {
                            for (const line of recurringLineIds) {
                                await this.env.services.orm.write(
                                    'welfare.recurring.line',
                                    [line.id],
                                    { state: 'disbursed' }
                                );
                            }

                            this.env.services.notification.add(
                                `Processed ${recurringLineIds.length} recurring welfare disbursement(s)`,
                                { type: 'success' }
                            );

                            // Check if ALL recurring lines are now disbursed
                            const remainingLines = await this.env.services.orm.searchRead(
                                'welfare.recurring.line',
                                [
                                    ['welfare_id', '=', welfareId],
                                    ['state', '!=', 'disbursed']
                                ],
                                ['id'],
                                {}
                            );

                            // If no remaining lines, update welfare.state to 'disbursed'
                            if (remainingLines.length === 0) {
                                await this.env.services.orm.write(
                                    'welfare',
                                    [welfareId],
                                    { state: 'disbursed' }
                                );

                                this.env.services.notification.add(
                                    `Welfare ${wfData.record_number} fully disbursed (all recurring lines completed)`,
                                    { type: 'success' }
                                );
                            }
                        }
                    }
                }
            } catch (error) {
                console.error("❌ [Welfare] Error updating state:", error);
                this.env.services.notification.add(
                    "Note: Welfare status not updated, but order will proceed",
                    { type: 'warning' }
                );
            }
        }
        
        // Continue with normal POS flow
        super.validateOrder(isForceValidate);
    },

    /**
     * Process equipment lines and add products to POS order
     */
    async processEquipmentLines(record, selectedOrder) {
        if (!this.hasEquipmentLines(record)) {
            return;
        }

        const equipmentLines = await this.fetchEquipmentLines(record);

        // console.log(`Equipment Lines:`, equipmentLines);

        for (const line of equipmentLines) {
            const equipmentLineId = line.id;
            const productId = line.product_id[0];
            const productName = line.product_id[1];
            const equipmentQty = line.quantity || 0;

            const orderLine = selectedOrder.orderlines.find(
                (ol) => ol.product.id === productId
            );

            // console.log(`Checking Product: ${productName}`);
            // console.log(`Equipment Qty: ${equipmentQty}`);
            // console.log(`OrderLine:`, orderLine);

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

                        // console.log(`✅ Updated ${productName}: ${equipmentQty} → ${newQty}`);
                    } catch (error) {
                        console.error(`❌ Failed to update ${productName}`, error);
                        this.env.services.notification.add(
                            `Error updating quantity for ${productName}`,
                            { type: "warning" }
                        );
                    }

                    return true;
                } else {
                    // console.log(`✅ Quantities already match for ${productName}`);

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
            // console.log("No equipment lines found for this record");

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
        
        // console.log("Equipment lines:", equipmentLines);
        
        return equipmentLines;
    }
});