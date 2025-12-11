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
        // console.log(this.pos);

        const shop = this.pos.config.id;

        const offset = (this.state.currentPage - 1) * this.state.limit;
            
        const result = await this.orm.call('pos.order', 'get_cheque_pos_order', [this.state.activeId, shop, offset, this.state.limit]);

        // console.log(result);
        
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
            // console.log(orderID);

            this.pos.pos_cheque_order_id = orderID;
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
            
            // console.log("Order Record:", record);
            
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
        // console.log("No record found with number:", this.state.record_number);

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
        // console.log("Record found:", orderRecord);
        
        // Process all record components
        await this.processPOSOrderLines(orderRecord, selectedOrder);
        await this.processPartner(orderRecord, selectedOrder);
        
        // Log current state and close popup
        // console.log("Record state:", orderRecord.state);

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
            // console.log("No order lines found for this record");

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
        
        // console.log("Order lines:", orderLines);

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
        
        // console.log(`Added ${product.display_name} (Qty: ${line.quantity || 1}, Price: ${price})`);
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