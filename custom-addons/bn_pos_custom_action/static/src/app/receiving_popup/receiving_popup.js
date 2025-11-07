

/** @odoo-module **/

import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
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
            
            return;
        } 
        // Process medical equipment records
        if (this.action_type === 'me') {
            this.pos.receive_voucher = true

            await this.processMedicalEquipmentRecord(selectedOrder);
        }
    }

    /**
     * Process medical equipment record
     */
    async processMedicalEquipmentRecord(selectedOrder) {
        console.log("Medical Equipment Record Number:", this.state.record_number);
        
        try {
            const record = await this.orm.searchRead(
                'medical.equipment',
                [['name', '=', this.state.record_number]],
                ['name', 'state', 'donee_id', 'medical_equipment_line_ids'],
                { limit: 1 }
            );

            console.log(record);

            if (!['draft', 'return'].includes(record[0].state)) {
                this.notification.add(
                    "Unauthorized Provisional Order State",
                    { type: 'warning' }
                );

                return
            } 
            
            console.log("Medical Equipment Record:", record);
            
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
     * Handle found medical equipment record
     */
    async handleRecordFound(equipmentRecord, selectedOrder) {
        console.log("Record found:", equipmentRecord);
        
        // Process all record components
        await this.processEquipmentLines(equipmentRecord, selectedOrder);
        this.addExtraOrderData(selectedOrder, equipmentRecord);
        await this.processPartner(equipmentRecord, selectedOrder);
        
        // Log current state and close popup
        console.log("Record state:", equipmentRecord.state);
        super.confirm();
        
        return equipmentRecord.state;
    }

    /**
     * Handle record not found scenario
     */
    handleRecordNotFound() {
        console.log("No record found with number:", this.state.record_number);
        this.notification.add(
            "Medical equipment record not found",
            { type: 'warning' }
        );
        return null;
    }

    /**
     * Handle processing errors
     */
    handleProcessingError(error) {
        console.error("Error processing medical equipment record:", error);
        this.notification.add(
            "Error processing equipment record",
            { type: 'danger' }
        );
        return null;
    }

    /**
     * Process equipment lines and add products to POS order
     */
    async processEquipmentLines(equipmentRecord, selectedOrder) {
        if (!this.hasEquipmentLines(equipmentRecord)) {
            return;
        }

        const equipmentLines = await this.fetchEquipmentLines(equipmentRecord);
        const addedProductsCount = await this.addProductsToOrder(equipmentLines, equipmentRecord, selectedOrder);
        
        this.notifyProductAdditionResult(addedProductsCount);
    }

    /**
     * Check if equipment has lines
     */
    hasEquipmentLines(equipmentRecord) {
        if (!equipmentRecord.medical_equipment_line_ids || equipmentRecord.medical_equipment_line_ids.length === 0) {
            console.log("No equipment lines found for this record");
            this.notification.add(
                "No products configured for this equipment",
                { type: 'warning' }
            );
            return false;
        }
        return true;
    }

    /**
     * Fetch equipment lines from database
     */
    async fetchEquipmentLines(equipmentRecord) {
        const equipmentLines = await this.orm.searchRead(
            'medical.equipment.line',
            [['id', 'in', equipmentRecord.medical_equipment_line_ids]],
            ['product_id', 'quantity', 'amounts'],
            {}
        );
        
        console.log("Equipment lines:", equipmentLines);
        return equipmentLines;
    }

    /**
     * Add products to POS order
     */
    async addProductsToOrder(equipmentLines, equipmentRecord, selectedOrder) {
        let addedProductsCount = 0;
        
        for (let line of equipmentLines) {
            if (await this.addProductLine(line, equipmentRecord, selectedOrder)) {
                addedProductsCount++;
            }
        }
        
        return addedProductsCount;
    }

    /**
     * Add individual product line to order
     */
    async addProductLine(line, equipmentRecord, selectedOrder) {
        if (!line.product_id || !line.product_id[0]) {
            return false;
        }

        const productId = line.product_id[0];
        const product = this.pos.db.get_product_by_id(productId);
        
        if (!product) {
            console.error("Product not found in POS database:", productId);
            return false;
        }

        const quantity = this.calculateProductPrice(line, equipmentRecord);
        // console.log(`Adding product ${product.display_name} with price ${price}`);
        
        selectedOrder.add_product(product, {
            quantity: quantity || 1,
            price:  line.amounts || product.lst_price,
            merge: false
        });
        
        // console.log(`Added ${product.display_name} (Qty: ${line.quantity || 1}, Price: ${price})`);
        return true;
    }

    /**
     * Calculate product price based on equipment state
     */
    calculateProductPrice(line, equipmentRecord) {
        let qty = line.quantity;
        
        // Apply negative price for return state
        if (equipmentRecord.state == 'return') {
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
                `Added ${addedProductsCount} products from equipment record`,
                { type: 'success' }
            );
        } else {
            console.error("No products could be added from equipment lines");
            this.notification.add(
                "No products found in equipment record",
                { type: 'warning' }
            );
        }
    }

    /**
     * Process partner assignment
     */
    async processPartner(equipmentRecord, selectedOrder) {
        if (!equipmentRecord.donee_id || !equipmentRecord.donee_id[0]) {
            return;
        }

        const partnerId = equipmentRecord.donee_id[0];
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
        
        console.log("Partner Data:", partnerData);
        
        if (partnerData && partnerData.length > 0) {
            this.pos.db.add_partners([partnerData[0]]);
            const partner = this.pos.db.get_partner_by_id(partnerId);
            console.log("Partner loaded to POS:", partner);
            return partner;
        }
        
        return null;
    }

    /**
     * Assign partner to order
     */
    assignPartnerToOrder(partner, selectedOrder) {
        selectedOrder.set_partner(partner);
        console.log("Partner set on order:", partner.name);
        this.notification.add(
            `Customer set to: ${partner.name}`,
            { type: 'info' }
        );
    }

    /**
     * Add extra data to order for reporting
     */
    addExtraOrderData(selectedOrder, equipmentRecord) {
        if (!selectedOrder.extra_data) {
            selectedOrder.extra_data = {};
        }
        
        selectedOrder.extra_data.medical_equipment = {
            record_number: equipmentRecord.name,
            equipment_state: equipmentRecord.state,
            equipment_id: equipmentRecord.id,
            scan_timestamp: new Date().toISOString(),
        };
        
        console.log("Extra order data added:", selectedOrder.extra_data.medical_equipment);
    }
    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
    }
}