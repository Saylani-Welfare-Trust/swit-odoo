/** @odoo-module */

import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";


// Microfinance installments (action_type 'mf') and recovery ('mf recovery').
patch(ReceivingPopup.prototype, {
    async confirmProgram(selectedOrder) {
        if (this.action_type === 'mf') {
            selectedOrder.set_receive_voucher(true);
            await this.processMicrofinanceRecord(selectedOrder);
            return true;
        }
        if (this.action_type === 'mf recovery') {
            selectedOrder.set_receive_voucher(true);
            await this.processMicrofinanceRecoveryRecord(selectedOrder);
            return true;
        }
        return super.confirmProgram(...arguments);
    },

    /**
     * Process Microfinance record
     */
    async processMicrofinanceRecord(selectedOrder) {
        try {
            const record = await this.orm.searchRead(
                'microfinance',
                ['|', ['name', '=', this.state.record_number], ['old_system_record', '=', this.state.record_number]],
                ['name', 'state', 'donee_id', 'microfinance_line_ids', 'microfinance_recovery_line_ids'],
                { limit: 1 }
            );
            if (!record.length) return this.handleRecordNotFound();
            
            if (record[0].microfinance_recovery_line_ids && record[0].microfinance_recovery_line_ids.length > 0) {
                this.notification.add(
                    "Recovery lines are created for this record. You cannot process installments.",
                    { type: 'danger' }
                );
                return;
            }
            if (record[0].state !== 'done') {
                this.notification.add("Unauthorized Request State", { type: 'warning' });
                return;
            }

            const microfinanceLineIds = await this.handleMicrofinanceLines(record[0], selectedOrder);
            if (!microfinanceLineIds) return;

            // Add partner to order
            if (record[0].donee_id && record[0].donee_id[0]) {
                const partnerId = record[0].donee_id[0];
                let partner = await this.getOrLoadPartner(partnerId);
                if (partner) {
                    this.assignPartnerToOrder(partner, selectedOrder);
                }
            }

            this.addExtraOrderData(selectedOrder, record[0], microfinanceLineIds);
            this._closeConfirmed();

        } catch (error) {
            this.handleProcessingError(error);
        }
    },

    /**
     * Process Microfinance Recovery record
     */
    async processMicrofinanceRecoveryRecord(selectedOrder) {
        try {
            const record = await this.orm.searchRead(
                'microfinance',
                ['|', ['name', '=', this.state.record_number], ['old_system_record', '=', this.state.record_number]],
                ['name', 'state', 'donee_id', 'microfinance_recovery_line_ids'],
                { limit: 1 }
            );

            if (!record.length) return this.handleRecordNotFound();
            // Recovery lines exist once the loan is sent to recovery.
            if (!['done', 'in_recovery'].includes(record[0].state)) {
                this.notification.add("Unauthorized Request State", { type: 'warning' });
                return;
            }

            const microfinanceRecoveryLineIds = await this.handleMicrofinanceRecoveryLines(record[0], selectedOrder);
            if (!microfinanceRecoveryLineIds) return;

            // Add partner to order
            if (record[0].donee_id && record[0].donee_id[0]) {
                const partnerId = record[0].donee_id[0];
                let partner = await this.getOrLoadPartner(partnerId);
                if (partner) {
                    this.assignPartnerToOrder(partner, selectedOrder);
                }
            }

            this.addExtraOrderData(selectedOrder, record[0], microfinanceRecoveryLineIds);
            this._closeConfirmed();

        } catch (error) {
            this.handleProcessingError(error);
        }
    },

    /**
     * Handle found microfinance record
     * - Loads ALL unpaid installment lines (sorted by due_date)
     * - Adds product with suggested amount (first due installment or current month if exists)
     * - POS user can modify the amount, payment will adjust installments accordingly
     */
    async handleMicrofinanceLines(record, selectedOrder) {
        if (!record.microfinance_line_ids || !record.microfinance_line_ids.length) {
            this.notification.add(
                "No microfinance lines found for this record",
                { type: 'warning' }
            );
            return;
        }

        // Fetch ALL unpaid lines (paid_amount = 0 or partial), sorted by due_date
        const lines = await this.orm.searchRead(
            'microfinance.line',
            [['id', 'in', record.microfinance_line_ids], ['state', '!=', 'paid']],
            ['id', 'amount', 'paid_amount', 'due_date', 'remaining_amount'],
            { order: 'due_date asc' }
        );

        if (!lines.length) {
            this.notification.add(
                "No unpaid microfinance installments found",
                { type: 'warning' }
            );
            return;
        }

        // Load installment product
        const mfProduct = await this.orm.searchRead(
            'product.product',
            [
                ['name', '=', this.pos.company.microfinance_intallement_product],
                ['detailed_type', '=', 'service'],
                ['available_in_pos', '=', true]
            ],
            ['id'],
            { limit: 1 }
        );

        if (!mfProduct.length) {
            await this.popup.add(ErrorPopup, {
                title: "Error",
                body: `${this.pos.company.microfinance_intallement_product} product not found or not available in POS.`
            });
            return;
        }

        const product = this.pos.db.get_product_by_id(mfProduct[0].id);
        if (!product) {
            await this.popup.add(ErrorPopup, {
                title: "Error",
                body: "Microfinance Installment product not loaded in POS session."
            });
            return;
        }

        // Current date values
        const now = new Date();
        const currentMonth = now.getMonth();
        const currentYear = now.getFullYear();

        // Find installment due this month (if any) to use as default amount
        let suggestedAmount = 0;
        const dueThisMonth = lines.find(l => {
            if (!l.due_date) return false;
            const [year, month, day] = l.due_date.split("-").map(Number);
            return month - 1 === currentMonth && year === currentYear;
        });

        if (dueThisMonth) {
            // Use remaining amount of current month installment as suggestion
            suggestedAmount = dueThisMonth.remaining_amount || (dueThisMonth.amount - (dueThisMonth.paid_amount || 0));
        } else {
            // No due this month, use first unpaid line's remaining amount as suggestion
            const firstUnpaid = lines[0];
            suggestedAmount = firstUnpaid.remaining_amount || (firstUnpaid.amount - (firstUnpaid.paid_amount || 0));
        }

        // Prepare all unpaid lines data for payment processing
        let allUnpaidLines = lines.map(line => ({
            id: line.id,
            amount: line.amount,
            paid_amount: line.paid_amount || 0,
            remaining_amount: line.remaining_amount || (line.amount - (line.paid_amount || 0)),
            due_date: line.due_date
        }));

        // Add single product line with suggested amount (POS user can modify)
        selectedOrder.add_product(product, {
            quantity: 1,
            price_extra: suggestedAmount
        });

        this.notification.add(
            `Loaded ${lines.length} unpaid installment(s). Suggested amount: ${suggestedAmount}. You can modify the amount.`,
            { type: "info" }
        );

        // Return all unpaid lines for payment processing
        return allUnpaidLines;
    },
    
    async handleMicrofinanceRecoveryLines(record, selectedOrder) {
        if (!record.microfinance_recovery_line_ids || !record.microfinance_recovery_line_ids.length) {
            this.notification.add(
                "No microfinance recovery lines found for this record",
                { type: 'warning' }
            );
            return;
        }

        const lines = await this.orm.searchRead(
            'microfinance.recovery.line',
            [['id', 'in', record.microfinance_recovery_line_ids], ['paid_amount', '=', 0]],
            ['id', 'amount', 'due_date'],
            {}
        );

        if (!lines.length) {
            this.notification.add(
                "No unpaid microfinance recovery installments found",
                { type: 'warning' }
            );
            return;
        }

        // Current date values
        const now = new Date();
        const currentMonth = now.getMonth();
        const currentYear = now.getFullYear();

        // Filter only lines due THIS month
        const dueThisMonth = lines.filter(l => {
            if (!l.due_date) return false;

            // parse in a safe way to prevent timezone shift
            const [year, month, day] = l.due_date.split("-").map(Number);
            const due = new Date(year, month - 1, day);

            return due.getMonth() === currentMonth && due.getFullYear() === currentYear;
        });

        if (!dueThisMonth.length) {
            this.notification.add(
                "No microfinance recovery installments due this month",
                { type: 'warning' }
            );
            return;
        }

        // Load installment product
        const mfProduct = await this.orm.searchRead(
            'product.product',
            [
                ['name', '=', this.pos.company.microfinance_intallement_product],
                ['detailed_type', '=', 'service'],
                ['available_in_pos', '=', true]
            ],
            ['id'],
            { limit: 1 }
        );

        if (!mfProduct.length) {
            await this.popup.add(ErrorPopup, {
                title: "Error",
                body: `${this.pos.company.microfinance_intallement_product} product not found or not available in POS.`
            });
            return;
        }

        const product = this.pos.db.get_product_by_id(mfProduct[0].id);
        if (!product) {
            await this.popup.add(ErrorPopup, {
                title: "Error",
                body: "Microfinance Installment product not loaded in POS session."
            });
            return;
        }

        let microfinanceRecoveryLineIds = [];

        // Add all installments due this month
        for (const line of dueThisMonth) {
            const orderline = selectedOrder.add_product(product, {
                quantity: 1,
                price_extra: line.amount
            });

            microfinanceRecoveryLineIds.push({ id: line.id, amount: line.amount });
        }

        this.notification.add(
            `Added ${dueThisMonth.length} installment(s) due this month`,
            { type: "success" }
        );

        return microfinanceRecoveryLineIds;
    },

    addExtraOrderData(selectedOrder, record, lineIds=null) {
        super.addExtraOrderData(...arguments);
        if (this.action_type === 'mf') {
            selectedOrder.extra_data.microfinance = {
                record_number: record.name,
                microfinance_state: record.state,
                microfinance_id: record.id,
                microfinance_line_ids: lineIds,
                scan_timestamp: new Date().toISOString(),
                security_desposit: false
            };
        }
        if (this.action_type === 'mf recovery') {
            selectedOrder.extra_data.microfinance = {
                record_number: record.name,
                microfinance_state: record.state,
                microfinance_id: record.id,
                microfinance_recovery_line_ids: lineIds,
                scan_timestamp: new Date().toISOString(),
                security_desposit: false
            };
        }
    },
});
