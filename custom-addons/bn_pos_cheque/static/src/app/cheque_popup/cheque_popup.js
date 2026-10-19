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
            
        const result = await this.orm.call('pos.order', 'get_cheque_pos_order', [this.state.activeId, shop, offset, this.state.limit]);
        
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

    async processReturn(orderID) {
        try {
            // 1. Fetch the return data from backend
            const returnData = await this.orm.call('pos.order', 'get_bounced_cheque_for_return', [orderID]);
            
            const selectedOrder = this.pos.get_order();
            
            // 2. Clear current order (optional, depends if you want a fresh return)
            // selectedOrder.remove_all_items(); 

            // 3. Add items as negative quantities
            for (let line of returnData.lines) {
                const product = this.pos.db.get_product_by_id(line.product_id);
                if (product) {
                    selectedOrder.add_product(product, {
                        quantity: -line.qty,
                        price: line.price_unit,
                    });
                }
            }

            // 4. Set Partner
            if (returnData.partner_id) {
                const partner = this.pos.db.get_partner_by_id(returnData.partner_id);
                if (partner) {
                    selectedOrder.set_partner(partner);
                }
            }

            // 5. Link the cheque details to the new return order
            selectedOrder.set_bank_name(returnData.bank_name);
            selectedOrder.set_cheque_number(`RETURN-${returnData.cheque_number}`);
            // Set the cheque state to cancel/draft so it doesn't show up as bounce anymore
            selectedOrder.set_pos_cheque_order_id(orderID); 

            // 6. Notify and close popup
            this.notification.add(
                `Return prepared for Cheque: ${returnData.cheque_number}`,
                { type: 'success' }
            );
            
            // Close the popup to let cashier select payment method (Cash)
            super.confirm();

        } catch (error) {
            console.error("Error preparing return:", error);
            this.notification.add(
                "Failed to prepare return for this cheque.",
                { type: 'danger' }
            );
        }
    }

    async searchChequeNumber(){
        const shop = this.pos.config.id;
        
        const text = this.searchInput.el.value

        const result = await this.orm.call('pos.order', 'get_cheque_pos_order_specific', [this.state.activeId, shop, text]);
        
        this.state.chequeorder = result.orders;
        this.state.totalRecords = result.total_count;
    }

    reDeposite(orderID){
        const result = this.orm.call('pos.order', 'redeposite_cheque', [this.state.activeId, orderID])
        .then(() => {
            this.get_pos_cheque(); // Refresh the data
        })
        .catch(error => {
            console.error("Error bouncing cheque:", error);
        });
    }
    
    async settleOrder(orderID){
        const selectedOrder = this.pos.get_order();
        
        await this.processPOSOrderRecord(selectedOrder, orderID);
        
        if (this.success) {
            selectedOrder.set_pos_cheque_order_id(orderID);
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
                ['name', 'state', 'partner_id', 'lines'],
                { limit: 1 }
            );
            
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
        
        selectedOrder.add_product(product, {
            quantity: -1*line.qty || -1,
            price_extra:  product.lst_price == 0 ? line.price_subtotal_incl : 0
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

    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
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