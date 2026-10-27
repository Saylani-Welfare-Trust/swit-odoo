/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

// Microfinance security deposits, installments and recoveries paid at the POS.
// The order is saved first; the microfinance records are only marked paid once
// the order is finalized, so a failed or cancelled validation leaves them as
// they were.
patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const mfData = order && order.extra_data && order.extra_data.microfinance;
        if (!mfData) {
            return super.validateOrder(...arguments);
        }

        order.set_source_document(mfData.record_number);
        const result = await super.validateOrder(...arguments);
        if (!order.finalized) {
            return result;
        }
        try {
            if (mfData.security_desposit) {
                await this._mfPaySecurityDeposit(order, mfData);
            } else if ((mfData.microfinance_line_ids || []).length) {
                await this._mfPayInstallments(order, mfData);
            } else {
                await this._mfPayRecovery(order, mfData);
            }
        } catch (error) {
            console.error("[Microfinance] Error updating the loan after payment:", error);
            this.env.services.notification.add(
                `Order ${order.name} is saved, but loan ${mfData.record_number} was not updated. Please inform the Microfinance team.`,
                { type: 'danger', sticky: true }
            );
        }
        return result;
    },

    _mfPaymentValues(order) {
        const payment_method = order.paymentlines[0]?.name || 'Cash';
        return {
            payment_method: payment_method == 'Cash' ? 'cash' : 'cheque',
            bank_name: order.bank_name || false,
            cheque_no: order.cheque_number || false,
            cheque_date: order.cheque_date || false,
            donee_id: order.get_partner()?.id || false,
            state: 'paid',
        };
    },

    async _mfPaySecurityDeposit(order, mfData) {
        const orm = this.env.services.orm;
        const values = this._mfPaymentValues(order);
        if (mfData.security_deposit_id) {
            // Update existing record
            await orm.write('microfinance.installment', [mfData.security_deposit_id], values);
            this.env.services.notification.add(`Deposit Received successfully`, { type: 'success' });
        } else {
            // Create new microfinance.installment record if it doesn't exist
            await orm.create('microfinance.installment', [{
                ...values,
                payment_type: 'security',
                microfinance_id: mfData.microfinance_id || false,
                amount: mfData.amount || 0,
                date: new Date().toISOString().split('T')[0],
            }]);
            this.env.services.notification.add(
                `Security Deposit record created and paid successfully`,
                { type: 'success' }
            );
        }
    },

    async _mfPayInstallments(order, mfData) {
        const orm = this.env.services.orm;
        const productName = this.pos.company.microfinance_intallement_product || 'Microfinance Installment';

        // Get the actual paid amount from the order line (user may have modified it)
        let actualPaidAmount = 0;
        for (const ol of order.get_orderlines()) {
            if (ol.product && ol.product.display_name === productName) {
                actualPaidAmount += ol.get_price_with_tax();
            }
        }

        // Distribute payment across installment lines (already sorted by due_date)
        let remainingPayment = actualPaidAmount;
        let processedLines = 0;
        for (const line of mfData.microfinance_line_ids) {
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

            await orm.write('microfinance.line', [line.id], {
                paid_amount: (line.paid_amount || 0) + paymentForThisLine,
                state: newState,
            });
            processedLines++;
        }

        // Create microfinance.installment record for tracking the installment payment
        await orm.create('microfinance.installment', [{
            ...this._mfPaymentValues(order),
            payment_type: 'installment',
            microfinance_id: mfData.microfinance_id || false,
            amount: actualPaidAmount,
            date: new Date().toISOString().split('T')[0],
        }]);

        this.env.services.notification.add(
            `Processed payment of ${actualPaidAmount} across ${processedLines} installment(s)`,
            { type: 'success' }
        );
    },

    async _mfPayRecovery(order, mfData) {
        const lines = mfData.microfinance_recovery_line_ids || [];
        for (const line of lines) {
            await this.env.services.orm.write('microfinance.recovery.line', [line.id], {
                paid_amount: line.amount,
                state: 'paid',
            });
        }
        this.env.services.notification.add(
            `Processed ${lines.length} microfinance recovery installment(s)`,
            { type: 'success' }
        );
    },
});
