/** @odoo-module **/

import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

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
        this.title = this.props.title || "Receive Order Details";
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
     * Hook for the program modules (bn_microfinance ...): handle their own
     * action_type and return true, or return super.
     */
    async confirmProgram(selectedOrder) {
        return false;
    }

    /**
     * Close the popup as confirmed. Patches cannot reach
     * AbstractAwaitablePopup.confirm through super, so they call this.
     */
    _closeConfirmed() {
        return super.confirm();
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
            return;
        }
        if (await this.confirmProgram(selectedOrder)) {
            return;
        }
        // Handle different action types
        if (this.action_type === 'qb') {
            selectedOrder.set_receive_voucher(false)
            
            await this.processQurbaniRecord(selectedOrder);
        } 
        if (this.action_type === 'dhs') {
            selectedOrder.set_receive_voucher(true)
            
            await this.processDHSRecord(selectedOrder);
        } 
        // Process medical equipment records
        if (this.action_type === 'me') {
            selectedOrder.set_receive_voucher(true)

            await this.processMedicalEquipmentRecord(selectedOrder);
        }
    }
    

    /**
     * Process Donation Home Service record
     */
    async processQurbaniRecord(selectedOrder) {
        try {

            let found = false;

            // ============================================
            // COW DISTRIBUTION
            // ============================================
            let cowRecords = await this.orm.searchRead(
                'qurbani.cow.distribution',
                [
                    ['qurbani_order_no', '=', this.state.record_number],
                    ['state', 'not in', ['delivered', 'not_applicable']]
                ],
                ['id']
            );

            if (cowRecords.length) {

                found = true;

                let cowIds = cowRecords.map(record => record.id);

                let cowAction = await this.orm.call(
                    'qurbani.cow.distribution',
                    'action_print_report',
                    [cowIds]
                );

                await this.env.services.action.doAction(cowAction);
            }

            // ============================================
            // GOAT DISTRIBUTION
            // ============================================
            let goatRecords = await this.orm.searchRead(
                'qurbani.goat.distribution',
                [
                    ['qurbani_order_no', '=', this.state.record_number],
                    ['state', 'not in', ['delivered', 'not_applicable']]
                ],
                ['id']
            );

            if (goatRecords.length) {

                found = true;

                let goatIds = goatRecords.map(record => record.id);

                let goatAction = await this.orm.call(
                    'qurbani.goat.distribution',
                    'action_print_report',
                    [goatIds]
                );

                await this.env.services.action.doAction(goatAction);
            }

            // ============================================
            // NOTHING FOUND
            // ============================================
            if (!found) {

                this.notification.add(
                    "No pending distribution records found",
                    { type: "danger" }
                );

                return;
            }

            super.confirm();

        } catch (error) {

            this.handleProcessingError(error);
        }
    }
    
    async processDHSRecord(selectedOrder) {
        try {
            const record = await this.orm.searchRead(
                'donation.home.service',
                [['name', '=', this.state.record_number]],
                ['name', 'state', 'donor_id', 'service_charges', 'donation_home_service_line_ids'],
                { limit: 1 }
            );

            if (record[0].state != 'gate_in') {
                this.notification.add(
                    "Unauthorized Provisional Order State",
                    { type: 'warning' }
                );

                return
            }
            
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
        try {
            const record = await this.orm.searchRead(
                'medical.equipment',
                [['name', '=', this.state.record_number]],
                ['name', 'state', 'donee_id', 'medical_equipment_line_ids','remaining_amount'],
                { limit: 1 }
            );

            if (!['sd_received', 'refund', 'donate'].includes(record[0].state)) {
                this.notification.add(
                    "Unauthorized Provisional Order State",
                    { type: 'warning' }
                );

                return
            }
            
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
     * Handle found record
     */
    async handleRecordFound(record, selectedOrder) {
        if (this.action_type === 'dhs') {
            await this.processDHSLines(record, selectedOrder);
            this.addExtraOrderData(selectedOrder, record);
            await this.processPartner(record, selectedOrder);
            super.confirm();
        }

        if (this.action_type === 'me') {
            const equipmentLineIds = await this.processEquipmentLines(record, selectedOrder);
            this.addExtraOrderData(selectedOrder, record, equipmentLineIds);   // <-- pass line ids through
            await this.processPartner(record, selectedOrder);
            super.confirm();
        }

        return record.state;
    }
    /**
     * Handle record not found scenario
     */
    handleRecordNotFound() {
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
            }
        }

        this.notifyProductAdditionResult(addedProductsCount);
    }


    /**
     * Process equipment lines and add products to POS order
     */
    async processEquipmentLines(record, selectedOrder) {
        if (!this.hasEquipmentLines(record)) {
            return [];
        }

        const equipmentLines = await this.fetchEquipmentLines(record);
        const addedLineIds = [];
        let addedProductsCount = 0;

        if (record.state !== 'donate') {
            for (let line of equipmentLines) {
                if (await this.addProductLine(line, record, selectedOrder)) {
                    addedProductsCount++;
                    addedLineIds.push({ id: line.id });
                }
            }
        } else {
            // donate-state path adds a single security-deposit product not tied to individual lines
            const result = await this.addProductsToOrder(equipmentLines, record, selectedOrder);
            addedProductsCount = result;
            // no per-line ids to track here since it's a lump-sum deposit product
        }

        this.notifyProductAdditionResult(addedProductsCount);
        return addedLineIds;
    }
    /**
     * Check if dhs has lines
     */
    hasDHSLines(record) {
        if (!record.donation_home_service_line_ids || record.donation_home_service_line_ids.length === 0) {
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
        
        return equipmentLines;
    }

    /**
     * Add products to POS order
     */
    async addProductsToOrder(lines, record, selectedOrder) {
        if (record.state !== 'donate'){
            let addedProductsCount = 0;
            console.log("Adding products for lines:", lines);
            for (let line of lines) {
                
                if (await this.addProductLine(line, record, selectedOrder)) {
                    addedProductsCount++;
                }
            }
        
            return addedProductsCount;  
        }
        else {
            console.log("Processing donate state for medical equipment. Adding security deposit product with remaining amount as price extra.");
                // 🚫 Check remaining amount first
            if (!record.remaining_amount || record.remaining_amount <= 0) {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: _t("Amount is already paid."),
                });
                return 0;
            }
            let addedProductsCount = 1;
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
                    
                    return 0;
                }
                
                // Add product to order
                selectedOrder.add_product(product, {
                    quantity: -1,
                    price_extra: record.remaining_amount,
                });
            }

            return addedProductsCount;      
        }
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
        
        if (this.action_type === 'me') {
            if (record.state == 'refund') {
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
                    console.log("Adding refund line with negative quantity and security deposit as price extra:", {
                        product: product.name,
                        quantity: quantity * -1,
                        price_extra: line.security_deposit,
                    });
                    
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
                    price_extra: line.security_deposit || product.lst_price || line.amount,
                });
            }

        }
        
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
        }
        
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

    /**
     * Add extra data to order for reporting
     */
    addExtraOrderData(selectedOrder, record, lineIds=null) {
        if (!selectedOrder.extra_data) {
            selectedOrder.extra_data = {};
        }
        
        if (this.action_type === 'qb') {
            selectedOrder.extra_data.qurbani = {
                record_number: record.name,
                qurbani_id: record.id,
                scan_timestamp: new Date().toISOString(),
            };
        }
        if (this.action_type === 'dhs') {
            selectedOrder.extra_data.dhs = {
                record_number: record.name,
                dhs_state: record.state,
                dhs_id: record.id,
                scan_timestamp: new Date().toISOString(),
            };
        }
        if (this.action_type === 'me') {
            selectedOrder.extra_data.medical_equipment = {
                record_number: record.name,
                equipment_state: record.state,
                equipment_id: record.id,
                equipment_line_ids: lineIds || [],   // <-- NEW
                scan_timestamp: new Date().toISOString(),
            };
        }
        
    }
}
