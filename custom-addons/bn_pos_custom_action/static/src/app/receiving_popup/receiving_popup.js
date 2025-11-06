// /** @odoo-module **/

// import { useState } from "@odoo/owl";
// import { useService } from "@web/core/utils/hooks";
// import { usePos } from "@point_of_sale/app/store/pos_hook";

// import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

// import {_t} from "@web/core/l10n/translation";


// export class ReceivingPopup extends AbstractAwaitablePopup {
//     static template = "bn_pos_custom_action.ReceivingPopup";

//     setup() {

//         this.pos = usePos();
//         this.orm = useService("orm");
//         this.popup = useService("popup");
//         this.report = useService("report");
//         this.notification = useService("notification");
        
//         this.title = this.props.title || "Module Name";
        
//         this.action_type = this.props.action_type
//         this.placeholder = this.props.placeholder

//         this.state = useState({
//             record_number: "",
//         });
//     }

//     updateRecordNumber(event) {
//         this.state.record_number = event.target.value;
//     }

//     canCancel() {
//         return true;
//     }

//     async cancel() {
//         if (this.canCancel()) {
//             super.cancel();
//         }
//     }


//     async confirm(){
//     const selectedOrder = this.pos.get_order();
    
//     if (this.active_type === 'dhs') {
//         return;
//     } else if (this.state.record_number.slice(0, 2).toLowerCase() === 'me') {
//         console.log("Medical Equipment Record Number:", this.state.record_number);
        
//         // Fixed: Added fields array and moved options to correct parameter
//         const record = await this.orm.searchRead(
//             'medical.equipment',
//             [['name', '=', this.state.record_number]],
//             ['name', 'state', 'partner_id', 'medical_equipment_line_ids'], // Fields to fetch
//             { limit: 1 } // Options
//         );
        
//         console.log("Medical Equipment Record:", record);
        
//         if (record && record.length > 0) {
//             console.log("Record found:", record[0]);
            
//             // Get the equipment lines with product details
//             if (record[0].medical_equipment_line_ids && record[0].medical_equipment_line_ids.length > 0) {
//                 const equipmentLines = await this.orm.searchRead(
//                     'medical.equipment.line',
//                     [['id', 'in', record[0].medical_equipment_line_ids]],
//                     ['product_id', 'quantity', 'price_unit', 'amount'], // Fields to fetch
//                     {} // Options
//                 );
                
//                 console.log("Equipment lines:", equipmentLines);
                
//                 let addedProductsCount = 0;
                
//                 // Add each product from equipment lines to POS order
//                 for (const line of equipmentLines) {
//                     if (line.product_id) {
//                         const productId = line.product_id[0];
//                         const product = this.pos.db.get_product_by_id(productId);
                        
//                         if (product) {
//                             // Add product with the quantity from equipment line
//                             selectedOrder.add_product(product, {
//                                 quantity: line.quantity || 1,
//                                 price: line.price_unit || product.lst_price,
//                                 merge: false
//                             });
                            
//                             console.log(`Added ${product.display_name} (Qty: ${line.quantity || 1})`);
//                             addedProductsCount++;
//                         } else {
//                             console.error("Product not found in POS database:", productId);
//                         }
//                     }
//                 }
                
//                 if (addedProductsCount > 0) {
//                     this.notification.add(
//                         `Added ${addedProductsCount} products from equipment record`,
//                         { type: 'success' }
//                     );
//                 } else {
//                     console.error("No products could be added from equipment lines");
//                     this.notification.add(
//                         "No products found in equipment record",
//                         { type: 'warning' }
//                     );
//                 }
//             } else {
//                 console.log("No equipment lines found for this record");
//                 this.notification.add(
//                     "No products configured for this equipment",
//                     { type: 'warning' }
//                 );
//             }
            
//             // Handle partner assignment
//             if (record[0].partner_id) {
//                 const partnerId = record[0].partner_id[0];
//                 const partnerName = record[0].partner_id[1];
                
//                 // Search for partner in POS database
//                 let partner = this.pos.db.get_partner_by_id(partnerId);
                
//                 if (!partner) {
//                     // If partner not in POS db, load it
//                     const partnerData = await this.orm.searchRead(
//                         'res.partner',
//                         [['id', '=', partnerId]],
//                         ['name', 'email', 'phone', 'street', 'city'], // Fields to fetch
//                         { limit: 1 } // Options
//                     );
                    
//                     if (partnerData && partnerData.length > 0) {
//                         // Add partner to POS database
//                         this.pos.db.add_partners([partnerData[0]]);
//                         partner = this.pos.db.get_partner_by_id(partnerId);
//                         console.log("Partner loaded to POS:", partner);
//                     }
//                 }
                
//                 if (partner) {
//                     selectedOrder.set_partner(partner);
//                     console.log("Partner set on order:", partner.name);
//                     this.notification.add(
//                         `Customer set to: ${partner.name}`,
//                         { type: 'info' }
//                     );
//                 } else {
//                     console.warn("Partner not found in POS database:", partnerId);
//                 }
//             }
            
//             // Add extra data to order for reporting
//             this.addExtraOrderData(selectedOrder, record[0]);
            
//             // Handle state logic
//             if (record[0].state === 'draft') {
//                 console.log("Record is in draft state");
//             } else if (record[0].state === 'confirmed') {
//                 console.log("Record is confirmed");
//             } else if (record[0].state === 'done') {
//                 console.log("Record is completed");
//             }
            
//             super.confirm();
//             return record[0].state;
            
//         } else {
//             console.log("No record found with number:", this.state.record_number);
//             this.notification.add(
//                 "Medical equipment record not found",
//                 { type: 'warning' }
//             );
//             return null;
//         }
//     }
// }


// // Method to add extra data to order for reporting
// addExtraOrderData(selectedOrder, equipmentRecord) {
//     // Create or extend the extra_data object
//     if (!selectedOrder.extra_data) {
//         selectedOrder.extra_data = {};
//     }
    
//     // Add medical equipment specific data
//     selectedOrder.extra_data.medical_equipment = {
//         record_number: equipmentRecord.name,
//         equipment_state: equipmentRecord.state,
//         equipment_id: equipmentRecord.id,
//         scan_timestamp: new Date().toISOString(),
//         source: 'medical_equipment_scan'
//     };
    
//     console.log("Extra order data added:", selectedOrder.extra_data);
// }
// }



/** @odoo-module **/

import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

import {_t} from "@web/core/l10n/translation";


export class ReceivingPopup extends AbstractAwaitablePopup {
    static template = "bn_pos_custom_action.ReceivingPopup";

    setup() {

        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.report = useService("report");
        this.notification = useService("notification");
        
        this.title = this.props.title || "Module Name";
        
        this.action_type = this.props.action_type;
        this.placeholder = this.props.placeholder;

        this.state = useState({
            record_number: "",
        });
    }

    updateRecordNumber(event) {
        this.state.record_number = event.target.value;
    }

    canCancel() {
        return true;
    }

    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
    }

    async confirm(){
        const selectedOrder = this.pos.get_order();
        
        if (this.active_type === 'dhs') {
            return;
        } else if (this.state.record_number.slice(0, 2).toLowerCase() === 'me') {
            console.log("Medical Equipment Record Number:", this.state.record_number);
            
            // Fixed: Added fields array and moved options to correct parameter
            const record = await this.orm.searchRead(
                'medical.equipment',
                [['name', '=', this.state.record_number]],
                ['name', 'state', 'donee_id', 'medical_equipment_line_ids'], // Fields to fetch
                { limit: 1 } // Options
            );
            if (record[0].state === 'draft') 
                console.log("Medical Equipment Record:", record);
                
                if (record && record.length > 0) {
                    console.log("Record found:", record[0]);
                    
                    // Get the equipment lines with product details
                    if (record[0].medical_equipment_line_ids && record[0].medical_equipment_line_ids.length > 0) {
                        const equipmentLines = await this.orm.searchRead(
                            'medical.equipment.line',
                            [['id', 'in', record[0].medical_equipment_line_ids]],
                            ['product_id', 'quantity', 'amount'], // Fields to fetch
                            {} // Options
                        );
                        
                        console.log("Equipment lines:", equipmentLines);
                        
                        let addedProductsCount = 0;
                        
                        // Add each product from equipment lines to POS order
                        for (const line of equipmentLines) {
                            if (line.product_id) {
                                const productId = line.product_id[0];
                                const product = this.pos.db.get_product_by_id(productId);
                                
                                if (product) {
                                    // Add product with the quantity from equipment line
                                    selectedOrder.add_product(product, {
                                        quantity: line.quantity || 1,
                                        price: line.amount || product.lst_price,
                                        merge: false
                                    });
                                    
                                    console.log(`Added ${product.display_name} (Qty: ${line.quantity || 1})`);
                                    addedProductsCount++;
                                } else {
                                    console.error("Product not found in POS database:", productId);
                                }
                            }
                        }
                        
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
                    } else {
                        console.log("No equipment lines found for this record");
                        this.notification.add(
                            "No products configured for this equipment",
                            { type: 'warning' }
                        );
                    }
                    this.addExtraOrderData(selectedOrder, record[0]);
                    console.log("Extra order data added:", selectedOrder.extra_data);
                    
                    // Handle partner assignment
                    if (record[0].donee_id) {
                        const partnerId = record[0].donee_id[0];
                        const partnerName = record[0].partnerId[1];
                        
                        // Search for partner in POS database
                        let partner = this.pos.db.get_partner_by_id(partnerId);
                        
                        if (!partner) {
                            // If partner not in POS db, load it
                            const partnerData = await this.orm.searchRead(
                                'res.partner',
                                [['id', '=', partnerId]],
                                ['name', 'email', 'phone', 'street', 'city'], // Fields to fetch
                                { limit: 1 } // Options
                            );
                            
                            console.log("Partner Data for extra_data:", selectedOrder.extra_data);
                            if (partnerData && partnerData.length > 0) {
                                // Add partner to POS database
                                this.pos.db.add_partners([partnerData[0]]);
                                partner = this.pos.db.get_partner_by_id(partnerId);
                                console.log("Partner loaded to POS:", partner);
                            }
                        }
                        
                        if (partner) {
                            selectedOrder.set_partner(partner);
                            console.log("Partner set on order:", partner.name);
                            this.notification.add(
                                `Customer set to: ${partner.name}`,
                                { type: 'info' }
                            );
                        } else {
                            console.warn("Partner not found in POS database:", partnerId);
                        }
                    }
                    
                    
                    // Handle state logic
                    if (record[0].state === 'draft') {
                        console.log("Record is in draft state");
                    } else if (record[0].state === 'confirmed') {
                        console.log("Record is confirmed");
                    } else if (record[0].state === 'done') {
                        console.log("Record is completed");
                    }
                    
                    super.confirm();
                    return record[0].state;
                    
                } else {
                    console.log("No record found with number:", this.state.record_number);
                    this.notification.add(
                        "Medical equipment record not found",
                        { type: 'warning' }
                    );
                    return null;
                }
            }
        }

    // Method to add extra data to order for reporting
    addExtraOrderData(selectedOrder, equipmentRecord) {
        // Create or extend the extra_data object
        if (!selectedOrder.extra_data) {
            selectedOrder.extra_data = {};
        }
        
        // Add medical equipment specific data
        selectedOrder.extra_data.medical_equipment = {
            record_number: equipmentRecord.name,
            equipment_state: equipmentRecord.state,
            equipment_id: equipmentRecord.id,
            scan_timestamp: new Date().toISOString(),
            
        };
        
        
    }
}






// /** @odoo-module **/

// import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
// import { patch } from "@web/core/utils/patch";

// patch(PaymentScreen, "medical_equipment_payment_screen", {
//     async validateOrder(isForceValidate) {
//         const order = this.currentOrder;
        
//         // Check if this order has medical equipment data
//         if (order.medical_equipment_data) {
//             try {
//                 // Update medical equipment state to 'payment_received'
//                 await this.env.services.orm.call(
//                     'medical.equipment',
//                     'write',
//                     [[order.medical_equipment_data.record_number]],
//                     { state: 'payment_received' }
//                 );
                
//                 console.log(`Medical equipment ${order.medical_equipment_data.record_number} state updated to payment_received`);
                
//                 // Optional: Show notification
//                 this.env.services.notification.add(
//                     `Medical equipment ${order.medical_equipment_data.record_number} marked as paid`,
//                     { type: 'success' }
//                 );
                
//             } catch (error) {
//                 console.error("Error updating medical equipment state:", error);
//                 // Continue with order validation even if update fails
//             }
//         }
        
//         // Call original method
//         return this._super(...arguments);
//     }
// });