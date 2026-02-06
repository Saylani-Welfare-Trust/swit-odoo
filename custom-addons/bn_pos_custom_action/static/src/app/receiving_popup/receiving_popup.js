/** @odoo-module **/

import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

export class ReceivingPopup extends AbstractAwaitablePopup {
    static template = "bn_pos_custom_action.ReceivingPopup";

    setup() {
        // Initialize services
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.report = useService("report");
        this.notification = useService("notification");
        
        // Set component properties
        this.title = this.props.title || "Module Name";
        this.action_type = this.props.action_type;
        this.placeholder = this.props.placeholder;
        
        this.wf_request_type = this.props.wf_request_type;

        // Initialize component state
        this.state = useState({
            record_number: "",
        });
    }

    /**
     * Update record number from input field
     */
    updateRecordNumber(event) {
        this.state.record_number = event.target.value;
    }

    /**
     * Check if cancel is allowed
     */
    canCancel() {
        return true;
    }

    /**
     * Handle cancel action
     */
    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
    }

    /**
     * Main confirm method - handles medical equipment record processing
     */
    async confirm() {
        const selectedOrder = this.pos.get_order();

        if (!this.state.record_number) {
            this.notification.add(
                "Please Enter a Number",
                { type: 'info' }
            );
        }
        
        // Handle different action types
        if (this.action_type === 'dhs') {
            this.pos.receive_voucher = true
            
            await this.processDHSRecord(selectedOrder);
        } 
        if (this.action_type === 'wf') {
            this.pos.receive_voucher = true
            
            await this.processWelfareRecord(selectedOrder);
        } 
        if (this.action_type === 'ad') {    
            this.pos.receive_voucher = true
            await this.processAdvanceDonationRecord(selectedOrder);
        } 
        // Process medical equipment records
        if (this.action_type === 'me') {
            this.pos.receive_voucher = true

            await this.processMedicalEquipmentRecord(selectedOrder);
        }
        // Process microfinance records
        if (this.action_type === 'mf') {
            this.pos.receive_voucher = true

            await this.processMicrofinanceRecord(selectedOrder);
        }
        if (this.action_type === 'mf recovery') {
            this.pos.receive_voucher = true

            await this.processMicrofinanceRecoveryRecord(selectedOrder);
        }
    }

    /**
     * Process Welfare record
     */
    async processAdvanceDonationRecord(selectedOrder) {
        try {
            // Fetch advance donation record
            const record = await this.orm.searchRead(
                'advance.donation',
                [['name', '=', this.state.record_number],
                 ['state', '=', 'approved']
            ],
                ['id', 'name', 'state', 'customer_id', 'remaining_amount', 'product_id', 'total_product_amount', 'paid_amount'],
                { limit: 1 }
            );

            if (!record.length) {
                this.notification.add("Advance donation record not found", { type: 'warning' });
                return;
            }

            const donationRecord = record[0];

            // Validate state must be 'approved'
            if (donationRecord.state !== 'approved') {
                this.notification.add(
                    `Unauthorized Request State: ${donationRecord.state}. Expected 'approved'.`,
                    { type: 'warning' }
                );
                return;
            }

            // Check if there's remaining amount to pay
            if (donationRecord.remaining_amount <= 0) {
                this.notification.add("No remaining amount to pay for this donation", { type: 'warning' });
                return;
            }

            // Get the product
            if (!donationRecord.product_id || !donationRecord.product_id[0]) {
                this.notification.add("No product found in advance donation record", { type: 'warning' });
                return;
            }

            const product = this.pos.db.get_product_by_id(donationRecord.product_id[0]);
            if (!product) {
                this.notification.add("Product not found in POS database", { type: 'warning' });
                return;
            }

            // Calculate amount per unit
            // Since it's a donation payment, we want to collect the remaining amount
            // We'll add the product with the remaining amount as the total
            const remainingAmount = donationRecord.remaining_amount;
            
            // Add product to POS order
            // We'll add it as a single line with the remaining amount
            // Using negative quantity to indicate it's a payment/collection
            selectedOrder.add_product(product, {
                quantity: 1, // Negative indicates payment collection
                price_extra: remainingAmount - product.lst_price, // Adjust price to match remaining amount
            });

            // Add partner to order if exists
            if (donationRecord.customer_id && donationRecord.customer_id[0]) {
                const partnerId = donationRecord.customer_id[0];
                let partner = await this.getOrLoadPartner(partnerId);
                if (partner) {
                    this.assignPartnerToOrder(partner, selectedOrder);
                }
            }

            // Add extra order data for payment_screen handling
            this.addAdvanceDonationExtraOrderData(selectedOrder, donationRecord);

            this.notification.add(
                `Added advance donation: ${donationRecord.name} - Remaining: ${remainingAmount}`,
                { type: "success" }
            );

            super.confirm();

        } catch (error) {
            this.handleProcessingError(error);
        }
    }

    /**
     * Add advance donation extra order data
     */
    addAdvanceDonationExtraOrderData(selectedOrder, record) {
        if (!selectedOrder.extra_data) {
            selectedOrder.extra_data = {};
        }
        
        selectedOrder.extra_data.advance_donation = {
            record_number: record.name,
            donation_state: record.state,
            donation_id: record.id,
            remaining_amount: record.remaining_amount,
            total_amount: record.total_product_amount,
            paid_amount: record.paid_amount,
            product_id: record.product_id[0],
            customer_id: record.customer_id ? record.customer_id[0] : null,
            scan_timestamp: new Date().toISOString(),
        };
        console.log("🟢 [Advance Donation] Added extra order data:", selectedOrder.extra_data);
    }



    async processWelfareRecord(selectedOrder) {
        try {
            // wf_request_type: 'one_time' or 'recurring'
            const isRecurring = this.wf_request_type === 'recurring';
            // console.log("Welfare Request Type:", this.wf_request_type, "Is Recurring:", isRecurring);

            const record = await this.orm.searchRead(
                'welfare',
                [['name', '=', this.state.record_number]],
                ['id', 'name', 'state', 'donee_id', 'welfare_line_ids', 'welfare_recurring_line_ids', 'order_type'],
                { limit: 1 }
            );

            if (!record.length) return this.handleRecordNotFound();

            const welfareRecord = record[0];

            // Validate state based on request type
            if (!isRecurring) {
                // One-time: state must be 'approve' (not 'recurring', not 'disbursed')
                if (welfareRecord.state !== 'approve') {
                    this.notification.add(
                        `Unauthorized Request State: ${welfareRecord.state}. Expected 'approve' for one-time disbursement.`,
                        { type: 'warning' }
                    );
                    return;
                }
            } else {
                // Recurring: state must be 'recurring'
                if (welfareRecord.state !== 'recurring') {
                    this.notification.add(
                        `Unauthorized Request State: ${welfareRecord.state}. Expected 'recurring' for recurring disbursement.`,
                        { type: 'warning' }
                    );
                    return;
                }
            }

            // Get current month/year
            const now = new Date();
            const currentMonth = now.getMonth();
            const currentYear = now.getFullYear();

            let welfareLineIds = [];
            let recurringLineIds = [];

            // Helper to group lines by product and sum quantity/amount
            function groupLinesByProduct(lines, isRecurring) {
                const grouped = {};
                for (const line of lines) {
                    const productId = line.product_id && line.product_id[0];
                    if (!productId) continue;
                    if (!grouped[productId]) {
                        grouped[productId] = {
                            productId,
                            quantity: 0,
                            amount: 0,
                            ids: [],
                        };
                    }
                    grouped[productId].quantity += line.quantity || 1;
                    grouped[productId].amount += isRecurring ? (line.amount || 0) : (line.total_amount || 0);
                    grouped[productId].ids.push(line.id);
                }
                return Object.values(grouped);
            }

            if (!isRecurring) {
                if (!welfareRecord.welfare_line_ids || !welfareRecord.welfare_line_ids.length) {
                    this.notification.add("No welfare lines found for this record", { type: 'warning' });
                    return;
                }
                const lines = await this.orm.searchRead(
                    'welfare.line',
                    [
                        ['id', 'in', welfareRecord.welfare_line_ids],
                        ['disbursement_category_id.name', '=', 'Cash'],
                    ],
                    ['id', 'product_id', 'total_amount', 'quantity', 'collection_date','state', 'disbursement_category_id'],
                    {}
                );
                // Filter by main welfare order_type
                // console.log("Welfare Record Order Type:", welfareRecord);
                const filteredLines = welfareRecord.order_type === 'one_time'
                    ? lines.filter(l => true) // all lines, since order_type is now on welfare
                    : [];
                // console.log("Filtered Lines:", filteredLines);
                const dueThisMonth = filteredLines.filter(l => {
                    if (!l.collection_date) return false;
                    const [year, month, day] = l.collection_date.split("-").map(Number);
                    // Only include if not disbursed
                    return month - 1 === currentMonth && year === currentYear && l.state !== 'disbursed';
                });
                if (!dueThisMonth.length) {
                    this.notification.add("No one-time welfare lines due this month", { type: 'warning' });
                    return;
                }
                // Group and add to POS
                const grouped = groupLinesByProduct(dueThisMonth, false);
                for (const group of grouped) {
                    const product = this.pos.db.get_product_by_id(group.productId);
                    if (product) {
                        // Calculate per-unit price and price_extra
                        const perUnitPrice = group.quantity ? (group.amount / group.quantity) : 0;
                        const priceExtra = perUnitPrice - product.lst_price;
                        selectedOrder.add_product(product, {
                            quantity: -1 * group.quantity,
                            price_extra: priceExtra,
                        });
                        for (const id of group.ids) {
                            welfareLineIds.push({ id, amount: group.amount });
                        }
                    }
                }
                if (!welfareLineIds.length) {
                    this.notification.add("No products could be added from welfare lines", { type: 'warning' });
                    return;
                }
                this.notification.add(
                    `Added ${grouped.length} one-time welfare item(s)`,
                    { type: "success" }
                );
            } else {
                const recurringLines = await this.orm.searchRead(
                    'welfare.recurring.line',
                    [
                        ['welfare_id', '=', welfareRecord.id],
                        ['state', '!=', 'disbursed'],
                        ['disbursement_category_id.name', '=', 'Cash'],
                    ],
                    ['id', 'product_id', 'amount', 'quantity', 'collection_date', 'state', 'disbursement_category_id'],
                    {}
                );
                const dueThisMonth = recurringLines.filter(l => {
                    if (!l.collection_date) return false;
                    const [year, month, day] = l.collection_date.split("-").map(Number);
                    // Only include if not disbursed
                    return month - 1 === currentMonth && year === currentYear && l.state !== 'disbursed';
                });
                if (!dueThisMonth.length) {
                    this.notification.add("No recurring welfare lines due this month", { type: 'warning' });
                    return;
                }
                // Group and add to POS
                const grouped = groupLinesByProduct(dueThisMonth, true);
                for (const group of grouped) {
                    const product = this.pos.db.get_product_by_id(group.productId);
                    if (product) {
                        // Calculate per-unit price and price_extra
                        const perUnitPrice = group.quantity ? (group.amount / group.quantity) : 0;
                        const priceExtra = perUnitPrice - product.lst_price;
                        selectedOrder.add_product(product, {
                            quantity:-1 * group.quantity,
                            price_extra: priceExtra,
                        });
                        for (const id of group.ids) {
                            recurringLineIds.push({ id, amount: group.amount });
                        }
                    }
                }
                if (!recurringLineIds.length) {
                    this.notification.add("No products could be added from recurring lines", { type: 'warning' });
                    return;
                }
                this.notification.add(
                    `Added ${grouped.length} recurring welfare item(s)`,
                    { type: "success" }
                );
            }

            // Add partner to order
            if (welfareRecord.donee_id && welfareRecord.donee_id[0]) {
                const partnerId = welfareRecord.donee_id[0];
                let partner = await this.getOrLoadPartner(partnerId);
                if (partner) {
                    this.assignPartnerToOrder(partner, selectedOrder);
                }
            }

            // Add extra order data for payment_screen handling
            this.addWelfareExtraOrderData(selectedOrder, welfareRecord, isRecurring, welfareLineIds, recurringLineIds);

            super.confirm();

        } catch (error) {
            this.handleProcessingError(error);
        }
    }

    /**
     * Add welfare extra order data
     */
    addWelfareExtraOrderData(selectedOrder, record, isRecurring, welfareLineIds, recurringLineIds) {
        if (!selectedOrder.extra_data) {
            selectedOrder.extra_data = {};
        }
        
        selectedOrder.extra_data.welfare = {
            record_number: record.name,
            welfare_state: record.state,
            welfare_id: record.id,
            is_recurring: isRecurring,
            welfare_line_ids: welfareLineIds,
            recurring_line_ids: recurringLineIds,
            scan_timestamp: new Date().toISOString(),
        };
    }

    /**
     * Process Microfinance record
     */
    async processMicrofinanceRecord(selectedOrder) {
        try {
            const record = await this.orm.searchRead(
                'microfinance',
                [['name', '=', this.state.record_number]],
                ['name', 'state', 'donee_id', 'microfinance_line_ids', 'microfinance_recovery_line_ids'],
                { limit: 1 }
            );
            // console.log(record);
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

            // Add partner to order
            if (record[0].donee_id && record[0].donee_id[0]) {
                const partnerId = record[0].donee_id[0];
                let partner = await this.getOrLoadPartner(partnerId);
                if (partner) {
                    this.assignPartnerToOrder(partner, selectedOrder);
                }
            }

            this.addExtraOrderData(selectedOrder, record[0], microfinanceLineIds);
            super.confirm();

        } catch (error) {
            this.handleProcessingError(error);
        }
    }

    /**
     * Process Microfinance Recovery record
     */
    async processMicrofinanceRecoveryRecord(selectedOrder) {
        try {
            const record = await this.orm.searchRead(
                'microfinance',
                [['name', '=', this.state.record_number]],
                ['name', 'state', 'donee_id', 'microfinance_recovery_line_ids'],
                { limit: 1 }
            );

            if (!record.length) return this.handleRecordNotFound();
            if (record[0].state !== 'done') {
                this.notification.add("Unauthorized Request State", { type: 'warning' });
                return;
            }

            const microfinanceRecoveryLineIds = await this.handleMicrofinanceRecoveryLines(record[0], selectedOrder);

            // Add partner to order
            // console.log(record);
            if (record[0].donee_id && record[0].donee_id[0]) {
                const partnerId = record[0].donee_id[0];
                let partner = await this.getOrLoadPartner(partnerId);
                if (partner) {
                    this.assignPartnerToOrder(partner, selectedOrder);
                }
            }

            this.addExtraOrderData(selectedOrder, record[0], microfinanceRecoveryLineIds);
            super.confirm();

        } catch (error) {
            this.handleProcessingError(error);
        }
    }

    /**
     * Process Donation Home Service record
     */
    async processDHSRecord(selectedOrder) {
        // console.log("Donation Home Service Record Number:", this.state.record_number);
        
        try {
            const record = await this.orm.searchRead(
                'donation.home.service',
                [['name', '=', this.state.record_number]],
                ['name', 'state', 'donor_id', 'service_charges', 'donation_home_service_line_ids'],
                { limit: 1 }
            );
            
            // console.log("Donation Home Service:", record);

            if (record[0].state != 'gate_in') {
                this.notification.add(
                    "Unauthorized Provisional Order State",
                    { type: 'warning' }
                );

                return
            } 
            
            // console.log("Medical Equipment Record:", record);
            
            if (record && record.length > 0) {
                await this.handleRecordFound(record[0], selectedOrder);
            } else {
                this.handleRecordNotFound();
            }
            
        } catch (error) {
            this.handleProcessingError(error);
        }
    }

    /**
     * Process medical equipment record
     */
    async processMedicalEquipmentRecord(selectedOrder) {
        // console.log("Medical Equipment Record Number:", this.state.record_number);
        
        try {
            const record = await this.orm.searchRead(
                'medical.equipment',
                [['name', '=', this.state.record_number]],
                ['name', 'state', 'donee_id', 'medical_equipment_line_ids'],
                { limit: 1 }
            );

            // console.log(record);

            // if (!['sd_received', 'return'].includes(record[0].state)) {
            if (!['sd_received', 'refund'].includes(record[0].state)) {
                this.notification.add(
                    "Unauthorized Provisional Order State",
                    { type: 'warning' }
                );

                return
            } 
            
            // console.log("Medical Equipment Record:", record);
            
            if (record && record.length > 0) {
                await this.handleRecordFound(record[0], selectedOrder);
            } else {
                this.handleRecordNotFound();
            }
            
        } catch (error) {
            this.handleProcessingError(error);
        }
    }

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
    }
    
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
    }

    /**
     * Handle found record
     */
    async handleRecordFound(record, selectedOrder) {
        // console.log("Record found:", record);
        
        if (this.action_type === 'dhs') {
            // Process all record components
            await this.processDHSLines(record, selectedOrder);
            this.addExtraOrderData(selectedOrder, record);
            await this.processPartner(record, selectedOrder);
            
            // Log current state and close popup
            // console.log("Record state:", record.state);

            super.confirm();
        }
        
        if (this.action_type === 'me') {
            // Process all record components
            await this.processEquipmentLines(record, selectedOrder);
            this.addExtraOrderData(selectedOrder, record);
            await this.processPartner(record, selectedOrder);
            
            // Log current state and close popup
            // console.log("Record state:", record.state);

            super.confirm();
        }

        return record.state;
    }

    /**
     * Handle record not found scenario
     */
    handleRecordNotFound() {
        // console.log("No record found with number:", this.state.record_number);

        this.notification.add(
            "Record not found",
            { type: 'warning' }
        );

        return null;
    }

    /**
     * Handle processing errors
     */
    handleProcessingError(error) {
        console.error("Error processing:", error);
        this.notification.add(
            "Error processing record",
            { type: 'danger' }
        );

        return null;
    }

    /**
     * Process dhs lines and add products to POS order
     */
    async processDHSLines(record, selectedOrder) {
        if (!this.hasDHSLines(record)) {
            return;
        }

        const dhsLines = await this.fetchDHSLines(record);
        let addedProductsCount = await this.addProductsToOrder(dhsLines, record, selectedOrder);
        
        // Add service charge line if present
        if (record.service_charges && parseFloat(record.service_charges) > 0) {
            // Fetch the service product
            const serviceProduct = await this.orm.searchRead(
                'product.product',
                [
                    ['name', '=', this.pos.company.donation_home_service_product],
                    ['detailed_type', '=', 'service'],
                    ['available_in_pos', '=', true]
                ],
                ['id'],
                { limit: 1 }
            );
            
            if (serviceProduct.length) {
                // Get the product from POS DB
                const product = this.pos.db.get_product_by_id(serviceProduct[0].id);
                
                if (!product) {
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: _t(`${this.pos.company.donation_home_service_product} product not loaded in POS session.`),
                    });
                    
                    return
                }
                
                // Add product to order
                selectedOrder.add_product(product, {
                    quantity: 1,
                    price_extra: record.service_charges,
                });

                addedProductsCount++;

                console.log(selectedOrder);
            }
        }

        this.notifyProductAdditionResult(addedProductsCount);
    }

    /**
     * Process equipment lines and add products to POS order
     */
    async processEquipmentLines(record, selectedOrder) {
        if (!this.hasEquipmentLines(record)) {
            return;
        }

        const equipmentLines = await this.fetchEquipmentLines(record);
        const addedProductsCount = await this.addProductsToOrder(equipmentLines, record, selectedOrder);
        
        this.notifyProductAdditionResult(addedProductsCount);
    }

    /**
     * Check if dhs has lines
     */
    hasDHSLines(record) {
        if (!record.donation_home_service_line_ids || record.donation_home_service_line_ids.length === 0) {
            // console.log("No donation home service lines found for this record");

            this.notification.add(
                "No products configured for this donation home service",
                { type: 'warning' }
            );
            return false;
        }

        return true;
    }
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
    }

    /**
     * Fetch equipment lines and add service charge product with custom price
     */
    async fetchDHSLines(record) {
        // Fetch equipment/product lines
        let dhsLines = await this.orm.searchRead(
            'donation.home.service.line',
            [['id', 'in', record.donation_home_service_line_ids]],
            ['product_id', 'quantity', 'amount'],
            {}
        );

        // console.log("DHS lines:", dhsLines);

        return dhsLines;
    }
    
    /**
     * Fetch equipment lines from database
     */
    async fetchEquipmentLines(record) {
        const equipmentLines = await this.orm.searchRead(
            'medical.equipment.line',
            [['id', 'in', record.medical_equipment_line_ids]],
            ['product_id', 'quantity', 'security_deposit'],
            {}
        );
        
        // console.log("Equipment lines:", equipmentLines);
        return equipmentLines;
    }

    /**
     * Add products to POS order
     */
    async addProductsToOrder(lines, record, selectedOrder) {
        let addedProductsCount = 0;
        
        for (let line of lines) {
            if (await this.addProductLine(line, record, selectedOrder)) {
                addedProductsCount++;
            }
        }
        
        return addedProductsCount;
    }

    /**
     * Add individual product line to order
     */
    async addProductLine(line, record, selectedOrder) {
        if (!line.product_id || !line.product_id[0]) {
            return false;
        }

        const productId = line.product_id[0];
        const product = this.pos.db.get_product_by_id(productId);
        
        if (!product) {
            console.error("Product not found in POS database:", productId);
            return false;
        }

        const quantity = this.calculateProductQuantity(line, record);
        // console.log(`Adding product ${product.display_name} with price ${price}`);
         
        if (this.action_type === 'me') {
            if (record.state == 'refund') {
                console.log(this.pos.company);

                // Fetch the service product
                const serviceProduct = await this.orm.searchRead(
                    'product.product',
                    [
                        ['name', '=', this.pos.company.medical_equipment_security_depsoit_product],
                        ['detailed_type', '=', 'service'],
                        ['available_in_pos', '=', true]
                    ],
                    ['id'],
                    { limit: 1 }
                );
                
                if (serviceProduct.length) {
                    // Get the product from POS DB
                    const product = this.pos.db.get_product_by_id(serviceProduct[0].id);
                    
                    if (!product) {
                        this.popup.add(ErrorPopup, {
                            title: _t("Error"),
                            body: _t(`${this.pos.company.medical_equipment_security_depsoit_product} product not loaded in POS session.`),
                        });
                        
                        return
                    }
                    
                    // Add product to order
                    selectedOrder.add_product(product, {
                        quantity: quantity * -1,
                        price_extra: line.security_deposit,
                    });
                }
            } else {
                if (product.lst_price > 0) {
                    selectedOrder.add_product(product, {
                        quantity: quantity || 1,
                    });
                }
                else if (product.lst_price <= 0) {
                    selectedOrder.add_product(product, {
                        quantity: quantity || 1,
                        price_extra: line.security_deposit || product.lst_price,
                    });
                }
            }
        }
        else {
            if (product.lst_price > 0) {
                selectedOrder.add_product(product, {
                    quantity: quantity || 1,
                });
            }
            else if (product.lst_price <= 0) {
                selectedOrder.add_product(product, {
                    quantity: quantity || 1,
                    price_extra: line.security_deposit || product.lst_price,
                });
            }

        }
        
        // console.log(`Added ${product.display_name} (Qty: ${line.quantity || 1}, Price: ${price})`);
        return true;
    }

    /**
     * Calculate product price based on state
     */
    calculateProductQuantity(line, record) {
        let qty = line.quantity;
        
        // Apply negative price for return state
        if (record.state == 'return') {
            qty = -1*qty;

            // console.log(`Using negative price for return state: ${qty}`);
        }

        // console.log(`Using standard price: ${Price}`);
        
        return qty;
    }

    /**
     * Notify user about product addition result
     */
    notifyProductAdditionResult(addedProductsCount) {
        if (addedProductsCount > 0) {
            this.notification.add(
                `Added ${addedProductsCount} products from record`,
                { type: 'success' }
            );
        } else {
            console.error("No products could be added from lines");
            this.notification.add(
                "No products found in record",
                { type: 'warning' }
            );
        }
    }

    /**
     * Process partner assignment
     */
    async processPartner(record, selectedOrder) {
        if (this.action_type == 'dhs') {
            if (!record.donor_id || !record.donor_id[0]) {
                return;
            }
    
            const partnerId = record.donor_id[0];
            let partner = await this.getOrLoadPartner(partnerId);
            
            if (partner) {
                this.assignPartnerToOrder(partner, selectedOrder);
            } else {
                console.warn("Partner not found in POS database:", partnerId);
            }
            
        }
        if (this.action_type == 'me') {
            if (!record.donee_id || !record.donee_id[0]) {
                return;
            }
    
            const partnerId = record.donee_id[0];
            let partner = await this.getOrLoadPartner(partnerId);
            
            if (partner) {
                this.assignPartnerToOrder(partner, selectedOrder);
            } else {
                console.warn("Partner not found in POS database:", partnerId);
            }
        }   
    }

    /**
     * Get partner from POS DB or load from server
     */
    async getOrLoadPartner(partnerId) {
        let partner = this.pos.db.get_partner_by_id(partnerId);
        
        if (!partner) {
            partner = await this.loadPartnerFromServer(partnerId);
        }
        
        return partner;
    }

    /**
     * Load partner data from server
     */
    async loadPartnerFromServer(partnerId) {
        const partnerData = await this.orm.searchRead(
            'res.partner',
            [['id', '=', partnerId]],
            ['name', 'email', 'phone', 'street', 'city'],
            { limit: 1 }
        );
        
        // console.log("Partner Data:", partnerData);
        
        if (partnerData && partnerData.length > 0) {
            this.pos.db.add_partners([partnerData[0]]);
            const partner = this.pos.db.get_partner_by_id(partnerId);
            
            // console.log("Partner loaded to POS:", partner);
            
            return partner;
        }
        
        return null;
    }

    /**
     * Assign partner to order
     */
    assignPartnerToOrder(partner, selectedOrder) {
        selectedOrder.set_partner(partner);
        
        // console.log("Partner set on order:", partner.name);
        
        this.notification.add(
            `Customer set to: ${partner.name}`,
            { type: 'info' }
        );
    }

    /**
     * Add extra data to order for reporting
     */
    addExtraOrderData(selectedOrder, record, lineIds=null) {
        if (!selectedOrder.extra_data) {
            selectedOrder.extra_data = {};
        }
        
        if (this.action_type === 'dhs') {
            selectedOrder.extra_data.dhs = {
                record_number: record.name,
                dhs_state: record.state,
                dhs_id: record.id,
                scan_timestamp: new Date().toISOString(),
            };

            // console.log("Extra order data added:", selectedOrder.extra_data.dhs);
        }
        if (this.action_type === 'me') {
            selectedOrder.extra_data.medical_equipment = {
                record_number: record.name,
                equipment_state: record.state,
                equipment_id: record.id,
                scan_timestamp: new Date().toISOString(),
            };

            // console.log("Extra order data added:", selectedOrder.extra_data.medical_equipment);
        }
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
        
    }

    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
    }
}