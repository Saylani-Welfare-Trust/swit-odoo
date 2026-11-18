/** @odoo-module **/

import { onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

import {_t} from "@web/core/l10n/translation";


export class ChequePopup extends AbstractAwaitablePopup {
    static template = "bn_pos_cheque.ChequePopup";

    async get_pos_cheque() {
        const shop = this.pos.config.id;

        const offset = (this.state.currentPage - 1) * this.state.limit;
            
        const result = await this.orm.call('pos.order', 'get_cheque_pos_order', [shop, offset, this.state.limit]);
        
        this.state.chequeorder = result.orders;
        this.state.totalRecords = result.total_count;
    }

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.searchInput = useRef("search-input");
        this.notification = useService("notification");
        
        this.title = this.props.title || "POS Cheque";
        
        this.state = useState({
            chequeorder: [],
            currentPage: 1,
            totalRecords: 0,
            limit: 10,
            isFilterVisible: false
        });

        onMounted(() => {
            this.get_pos_cheque();
            this.state.isFilterVisible = false
        });
    }

    next = () => {
        if (this.state.currentPage * this.state.limit < this.state.totalRecords) {
            this.state.currentPage += 1;
            
            this.get_pos_cheque();
        }
    }

    previous = () => {
        if (this.state.currentPage > 1) {
            this.state.currentPage -= 1;
            
            this.get_pos_cheque();
        }
    }

    async searchChequeNumber(){
        const shop = this.pos.config.id;
        
        const text = this.searchInput.el.value

        this.state.currentPage = 1;
        const result = await this.orm.call('pos.order', 'get_cheque_pos_order_specific', [shop, text]);
        
        this.state.chequeorder = result.orders;
        this.state.totalRecords = result.total_count;
    }

    async reDeposite(orderID){
        await this.orm.call('pos.order', 'redeposite_cheque', [orderID, this.pos.config.id]);
        this.notification.add(_t("Cheque re-deposited"), { type: 'success' });
        await this.get_pos_cheque(); // Refresh the data
    }
    
    async settleOrder(orderID){
        const selectedOrder = this.pos.get_order();
        
        await this.processPOSOrderRecord(selectedOrder, orderID);
        
        if (this.success) {
            selectedOrder.set_pos_cheque_order_id(orderID);
            selectedOrder.set_return_cheque(this.returnCheque);
        }
    }

    /**
     * Process pos order record
     */
    async processPOSOrderRecord(selectedOrder, orderID) {
        try {
            const record = await this.orm.searchRead(
                'pos.order',
                [['id', '=', orderID]],
                ['name', 'state', 'partner_id', 'lines', 'bank_name', 'cheque_number', 'cheque_date'],
                { limit: 1 }
            );

            if (record && record.length > 0) {
                this.returnCheque = {
                    bank_name: record[0].bank_name || "",
                    cheque_number: record[0].cheque_number || "",
                    cheque_date: record[0].cheque_date || "",
                };

                await this.handleRecordFound(record[0], selectedOrder);
            } else {
                this.handleRecordNotFound();
            }
        } catch (error) {
            this.handleProcessingError(error);
        }
    }

    /**
     * Handle record not found scenario
     */
    handleRecordNotFound() {
        this.notification.add(
            "Order record not found",
            { type: 'warning' }
        );
        return null;
    }

    /**
     * Handle processing errors
     */
    handleProcessingError(error) {
        console.error("Error processing pos order record:", error);
        this.notification.add(
            "Error processing order record",
            { type: 'danger' }
        );
        return null;
    }

    /**
     * Handle found pos order record
     */
    async handleRecordFound(orderRecord, selectedOrder) {
        // Process all record components
        await this.processPOSOrderLines(orderRecord, selectedOrder);
        await this.processPartner(orderRecord, selectedOrder);
        
        // Log current state and close popup
        super.confirm();
        
        return orderRecord.state;
    }

    /**
     * Process order lines and add products to POS order
     */
    async processPOSOrderLines(orderRecord, selectedOrder) {
        if (!this.hasPOSOrderLines(orderRecord)) {
            return;
        }

        const orderLines = await this.fetchPOSOrderLines(orderRecord);
        const addedProductsCount = await this.addProductsToOrder(orderLines, selectedOrder);
        
        this.notifyProductAdditionResult(addedProductsCount);
    }

    /**
     * Check if order has lines
     */
    hasPOSOrderLines(orderRecord) {
        if (!orderRecord.lines || orderRecord.lines.length === 0) {
            this.notification.add(
                "No products configured for this order",
                { type: 'warning' }
            );
            return false;
        }
        return true;
    }

    /**
     * Fetch order lines from database
     */
    async fetchPOSOrderLines(orderRecord) {
        const orderLines = await this.orm.searchRead(
            'pos.order.line',
            [['id', 'in', orderRecord.lines]],
            ['product_id', 'qty', 'price_subtotal_incl'],
            {}
        );
        
        return orderLines;
    }

    /**
     * Add products to POS order
     */
    async addProductsToOrder(orderLines, selectedOrder) {
        let addedProductsCount = 0;
        
        for (let line of orderLines) {
            if (await this.addProductLine(line, selectedOrder)) {
                addedProductsCount++;
            }
        }
        
        return addedProductsCount;
    }

    /**
     * Add individual product line to order
     */
    async addProductLine(line, selectedOrder) {
        if (!line.product_id || !line.product_id[0]) {
            return false;
        }

        const productId = line.product_id[0];
        const product = this.pos.db.get_product_by_id(productId);
        
        if (!product) {
            console.error("Product not found in POS database:", productId);
            return false;
        }
        
        // give back exactly what was paid for the line
        const qty = line.qty || 1;
        selectedOrder.add_product(product, {
            quantity: -qty,
            price: line.price_subtotal_incl / qty,
            merge: false,
        });
        
        return true;
    }

    /**
     * Notify user about product addition result
     */
    notifyProductAdditionResult(addedProductsCount) {
        if (addedProductsCount > 0) {
            this.success = true

            this.notification.add(
                `Added ${addedProductsCount} products from order record`,
                { type: 'success' }
            );
        } else {
            console.error("No products could be added from order lines");
            this.notification.add(
                "No products found in order record",
                { type: 'warning' }
            );
        }
    }

    /**
     * Process partner assignment
     */
    async processPartner(orderRecord, selectedOrder) {
        if (!orderRecord.partner_id || !orderRecord.partner_id[0]) {
            return;
        }

        const partnerId = orderRecord.partner_id[0];
        let partner = await this.getOrLoadPartner(partnerId);
        
        if (partner) {
            this.assignPartnerToOrder(partner, selectedOrder);
        } else {
            console.warn("Partner not found in POS database:", partnerId);
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
        
        if (partnerData && partnerData.length > 0) {
            this.pos.db.add_partners([partnerData[0]]);
            const partner = this.pos.db.get_partner_by_id(partnerId);
            
            return partner;
        }
        
        return null;
    }

    /**
     * Assign partner to order
     */
    assignPartnerToOrder(partner, selectedOrder) {
        selectedOrder.set_partner(partner);
        
        this.notification.add(
            `Customer set to: ${partner.name}`,
            { type: 'info' }
        );
    }

    canCancel() {
        return true;
    }

    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
    }
}