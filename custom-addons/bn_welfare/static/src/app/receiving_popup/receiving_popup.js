/** @odoo-module */

import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";


// Welfare disbursement (action_type 'wf') and return ('wf_return').
patch(ReceivingPopup.prototype, {
    setup() {
        super.setup(...arguments);
        this.wf_request_type = this.props.wf_request_type;
    },

    async confirmProgram(selectedOrder) {
        if (this.action_type === 'wf_return') {
            // Return the welfare number and close the popup
            this.props.resolve({ confirmed: true, payload: this.state.record_number });
            this.cancel();
            return true;
        }
        if (this.action_type === 'wf') {
            selectedOrder.set_receive_voucher(true);
            await this.processWelfareRecord(selectedOrder);
            return true;
        }
        return super.confirmProgram(...arguments);
    },

    /**
     * Process Welfare record
     */
    async processWelfareRecord(selectedOrder) {
        try {
            // wf_request_type: 'one_time' or 'recurring'
            const isRecurring = this.wf_request_type === 'recurring';

            if (
                selectedOrder.extra_data &&
                selectedOrder.extra_data.welfare &&
                selectedOrder.extra_data.welfare.disbursement_status === "pending"
            ) {
                this.notification.add("A welfare payment is already loaded on this order.", { type: "warning" });
                return false;
            }

            const record = await this.orm.searchRead(
                'welfare',
                ['|', ['name', '=', this.state.record_number], ['old_system_id', '=', this.state.record_number]],
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

            // Get the company-configured welfare product
            const wfProduct = await this.orm.searchRead(
                'product.product',
                [
                    ['name', '=', this.pos.company.welfare_product],
                    ['detailed_type', '=', 'service'],
                    ['available_in_pos', '=', true]
                ],
                ['id'],
                { limit: 1 }
            );

            if (!wfProduct.length) {
                await this.popup.add(ErrorPopup, {
                    title: "Error",
                    body: `${this.pos.company.welfare_product} product not found or not available in POS.`
                });
                return;
            }

            const configuredProduct = this.pos.db.get_product_by_id(wfProduct[0].id);
            if (!configuredProduct) {
                await this.popup.add(ErrorPopup, {
                    title: "Error",
                    body: "Welfare product not loaded in POS session."
                });
                return;
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
                        ['collection_point', '=', 'branch'],
                        ['state', '=', 'draft'],
                    ],
                    ['id', 'product_id', 'total_amount', 'quantity', 'collection_date','state', 'disbursement_category_id'],
                    {}
                );
                // Filter by main welfare order_type
                const filteredLines = welfareRecord.order_type === 'one_time'
                    ? lines.filter(l => true) // all lines, since order_type is now on welfare
                    : [];
                const dueThisMonth = filteredLines.filter(l => {
                    if (!l.collection_date) return false;
                    const [year, month, day] = l.collection_date.split("-").map(Number);
                    return month - 1 === currentMonth && year === currentYear && l.state === 'draft';
                });
                if (!dueThisMonth.length) {
                    this.notification.add("No one-time welfare lines due this month", { type: 'warning' });
                    return;
                }
                // Group lines (kept for welfareLineIds tracking), add the configured product instead of per-line products
                const grouped = groupLinesByProduct(dueThisMonth, false);
                for (const group of grouped) {
                    // Calculate per-unit price and price_extra
                    const perUnitPrice = group.quantity ? (group.amount / group.quantity) : 0;
                    const priceExtra = perUnitPrice - configuredProduct.lst_price;
                    selectedOrder.add_product(configuredProduct, {
                        quantity: -1 * group.quantity,
                        price_extra: priceExtra,
                    });
                    for (const id of group.ids) {
                        welfareLineIds.push({ id, amount: group.amount });
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
                        ['state', '=', 'draft'],
                        ['disbursement_category_id.name', '=', 'Cash'],
                        ['collection_point', '=', 'branch'],
                    ],
                    ['id', 'product_id', 'amount', 'quantity', 'collection_date', 'state', 'disbursement_category_id'],
                    {}
                );
                const dueThisMonth = recurringLines.filter(l => {
                    if (!l.collection_date) return false;
                    const [year, month, day] = l.collection_date.split("-").map(Number);
                    return month - 1 === currentMonth && year === currentYear && l.state === 'draft';
                });
                if (!dueThisMonth.length) {
                    this.notification.add("No recurring welfare lines due this month", { type: 'warning' });
                    return;
                }
                // Group lines (kept for recurringLineIds tracking), add the configured product instead of per-line products
                const grouped = groupLinesByProduct(dueThisMonth, true);
                for (const group of grouped) {
                    // Calculate per-unit price and price_extra
                    const perUnitPrice = group.quantity ? (group.amount / group.quantity) : 0;
                    const priceExtra = perUnitPrice - configuredProduct.lst_price;
                    selectedOrder.add_product(configuredProduct, {
                        quantity:-1 * group.quantity,
                        price_extra: priceExtra,
                    });
                    for (const id of group.ids) {
                        recurringLineIds.push({ id, amount: group.amount });
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

            this._closeConfirmed();
            return true;

        } catch (error) {
            this.handleProcessingError(error);
            return false;
        }
    },

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
            state : 'draft',
            welfare_id: record.id,
            is_recurring: isRecurring,
            welfare_line_ids: welfareLineIds,
            recurring_line_ids: recurringLineIds,
            scan_timestamp: new Date().toISOString(),
            
            // New fields for return and payment handling
            is_welfare_order: true,           // Marks this as a welfare order
            order_type: isRecurring ? 'recurring_welfare' : 'one_time_welfare',  // Type of welfare order
            disbursement_status: 'pending',   // pending, completed, failed
            return_status: 'none',            // none, pending, completed, failed
            payment_status: 'pending',        // pending, completed, partially_completed, failed
            
            // For tracking returns related to this welfare order
            return_order_ids: [],             // Store IDs of return orders
            original_disbursement_date: new Date().toISOString(),
            
            // For payment tracking
            total_disbursed_amount: 0,        // Total amount disbursed
            total_returned_amount: 0,         // Total amount returned
            net_amount: 0,                    // Net amount (disbursed - returned)
            
            // Line item tracking
            disbursed_line_ids: welfareLineIds.map(line => ({
                id: line.id,
                amount: line.amount || 0,
                disbursed_at: new Date().toISOString(),
                status: 'disbursed'
            })),
            
            recurring_details: isRecurring ? {
                recurring_id: record.id,
                recurring_line_ids: recurringLineIds,
                current_cycle: record.current_cycle || 1,
                next_cycle_date: record.next_cycle_date || null
            } : null
        };
    },
});
