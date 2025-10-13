





/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { CustomButtonPopup } from "@sm_point_of_sale_apps/js/CustomButtonPopup/CustomButtonPopup";
import { InstallmentPopup } from "@pos_microfinance_loan/js/button";
import { DisbursementPopup } from "@bn_welfare/js/disbursementPopup";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Order } from "@point_of_sale/app/store/models";

// ==================================================
// 🔹 Extend Order to hold DHS reference, location data, and operation type
// ==================================================
Order.prototype.set_dhs_reference = function (dhsRef) {
    this.dhs_ref = dhsRef;
};

Order.prototype.get_dhs_reference = function () {
    return this.dhs_ref;
};

Order.prototype.set_dhs_source_location = function (locationId) {
    this.dhs_source_location_id = locationId;
};

Order.prototype.get_dhs_source_location = function () {
    return this.dhs_source_location_id;
};

Order.prototype.set_is_dhs_order = function (isDhs) {
    this.is_dhs_order = isDhs;
};

Order.prototype.get_is_dhs_order = function () {
    return this.is_dhs_order;
};

Order.prototype.set_scan_card_data = function (reference, locationId, pickingTypeId) {
    this.dhs_ref = reference;
    this.source_location_id = locationId;  // Match Python field name
    this.picking_type_id = pickingTypeId;  // Match Python field name
    this.is_scan_card_order = true;        // Match Python field name
};

Order.prototype.get_scan_card_data = function () {
    return {
        reference: this.dhs_ref,
        location_id: this.source_location_id,
        picking_type_id: this.picking_type_id,
        is_scan_card: this.is_scan_card_order
    };
};

// Single export_as_JSON method that handles both DHS and scan card orders
const superExportAsJSON = Order.prototype.export_as_JSON;
Order.prototype.export_as_JSON = function () {
    const json = superExportAsJSON.apply(this, arguments);
    
    // Handle scan card orders (priority)
    if (this.is_scan_card_order) {
        json.dhs_ref = this.dhs_ref;
        json.source_location_id = this.source_location_id;
        json.picking_type_id = this.picking_type_id;
        json.is_scan_card_order = this.is_scan_card_order;
    } 
    // Handle regular DHS orders
    else if (this.get_dhs_reference()) {
        json.dhs_ref = this.get_dhs_reference();
        json.dhs_source_location_id = this.get_dhs_source_location();
        json.is_dhs_order = this.get_is_dhs_order();
    }
    
    return json;
};

export class CustomScanCard extends Component {
    static template = "sm_point_of_sale_apps.CustomScanCard";

    setup() {
        super.setup();
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.report = useService("report");
        this.action = useService("action");
    }

    async onClick() {
        const { confirmed, payload: data } = await this.popup.add(CustomButtonPopup, {
            title: _t("Scan Card"),
        });

        console.log(`Hit Disbursement ${JSON.stringify(data)}`);

        if (confirmed) {
            // DHS SPECIFIC LOGIC - Use scan card data for live stock operations
            if (data.type_value == "dhs") {
                const dhsId = data.DonationBox_id || data.donation_box_id || data.dhs_value;
                
                if (dhsId) {
                    console.log('DHS detected, ID:', dhsId);
                    await this.fetchAndAddDHSProducts(dhsId, true); // true = use scan card mode
                }
            }
            // Scan card with DHS value - Use sca
            // n card data for live stock operations
            else if (data.type_value == "scan_card" && data.scan_card_value && data.scan_card_value.startsWith('DHS/')) {
                const dhsId = data.scan_card_value;
                console.log('DHS scan card detected:', dhsId);
                await this.fetchAndAddDHSProducts(dhsId, true); // true = use scan card mode
            }
            // Your existing code for other types
            else if (data.type_value == "med_eq") {
                this.report.doAction("sm_point_of_sale_apps.medical_equipment_report_action", [
                    data.DonationBox_id,
                ]);
            }
            else if(data.scan_card_value) {
                let partner = this.pos.db.get_partner_by_barcode(data.scan_card_value);
                let order = this.pos.get_order();
                if (order && partner) {
                    order.set_partner(partner);
                }
            }
            else if(data.cnic_number_value) {
                let partner = this.pos.db.get_partner_by_barcode(data.scan_card_value);
                let order = this.pos.get_order();
                if (order && partner) {
                    order.set_partner(partner);
                }
                await this.orm.call('mfd.loan.request', "check_loan_ids", [data.cnic_number_value]).then((data) => {
                    if (data.status === 'error') {
                        this.popup.add(ErrorPopup, {
                            title: _t("Error"),
                            body: data.body,
                        });
                    }
                    if (data.status === 'success') {
                        this.popup.add(InstallmentPopup, {
                            loan_ids: data.loan_ids,
                            bank_ids: data.bank_ids
                        });
                    }
                });
            }
            else if(data.disbursement_value) {
                let partner = this.pos.db.get_partner_by_barcode(data.scan_card_value);
                let order = this.pos.get_order();
                if (order && partner) {

                    order.set_partner(partner);
                }

                if (data.order_type_value == 'one_time') {
                    await this.orm.call('disbursement.request', "check_disbursement_ids", [data.disbursement_value]).then((data) => {
                        if (data.status === 'error') {
                            this.popup.add(ErrorPopup, {
                                title: _t("Error"),
                                body: data.body,
                            });
                        }
                        if (data.status === 'success') {
                            this.popup.add(DisbursementPopup, {
                                disbursement_ids: data.disbursement_ids,
                                collection_ids: data.collection_ids
                            });
                        }
                    });
                }
                else {
                    await this.orm.call('disbursement.request', "check_recurring_disbursement_ids", [data.disbursement_value]).then((data) => {
                        if (data.status === 'error') {
                            this.popup.add(ErrorPopup, {
                                title: _t("Error"),
                                body: data.body,
                            });
                        }
                        if (data.status === 'success') {
                            this.popup.add(DisbursementPopup, {
                                disbursement_ids: data.disbursement_ids,
                                collection_ids: data.collection_ids
                            });
                        }
                    });
                }
            }
            else if(data.key_value) {
                let partner = this.pos.db.get_partner_by_barcode(data.scan_card_value);
                let order = this.pos.get_order();
                if (order && partner) {
                    order.set_partner(partner);
                }

                const payroll = {
                    'key': data.key_value,
                    'amount': data.collection_amount_value
                }

                await this.orm.call('key.issuance', "set_donation_amount", [payroll]).then((data) => {
                    if (data.status === 'error') {
                        this.popup.add(ErrorPopup, {
                            title: _t("Error"),
                            body: data.body,
                        });
                    }
                    if (data.status === 'success') {
                        this.notification.add(_t("Amount Recorded Successful"), {
                            type: "info",
                        });
                        this.report.doAction("sm_point_of_sale_apps.donationbox_slip_report_action", [
                            data.DonationBox_id,
                        ]);
                    }
                });
            }
        }
    }

    async fetchAndAddDHSProducts(dhsName, useScanCardMode = false) {
        console.log('=== fetchAndAddDHSProducts() STARTED ===', dhsName, 'ScanCardMode:', useScanCardMode);
        
        if (!dhsName || dhsName.trim() === '') {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("Please provide a valid DHS reference number"),
            });
            return;
        }

        try {
            // Fetch DHS data from server
            let dhsData;
            try {
                dhsData = await this.orm.call(
                    'donation.home.service',
                    'fetch_dhs_products',
                    [dhsName.trim()]
                );
                console.log('Server response received:', dhsData);
            } catch (serverError) {
                console.error('Server call failed:', serverError);
                throw new Error(_t('Server error: Could not fetch DHS data. Please check the DHS reference.'));
            }

            if (!dhsData) {
                throw new Error(_t('No response from server'));
            }

            if (!dhsData.success) {
                throw new Error(dhsData.error || _t('Failed to fetch DHS data'));
            }

            // Get current order or create new one
            let order = this.pos.get_order();
            if (!order) {
                order = this.pos.add_new_order();
            }

            // 🔹 Set order data based on mode
            if (useScanCardMode) {
                // Use scan card mode with live stock location and custom operation type
                order.set_scan_card_data(
                    dhsData.dhs_name, 
                    dhsData.source_location_id, 
                    dhsData.picking_type_id
                );
                
                console.log('Scan card order created:');
                console.log('Reference:', dhsData.dhs_name);
                console.log('Location ID:', dhsData.source_location_id);
                console.log('Picking Type ID:', dhsData.picking_type_id);
            } else {
                // Use regular DHS mode
                order.set_dhs_reference(dhsName);
                order.set_is_dhs_order(true);
                
                if (dhsData.source_location_id) {
                    order.set_dhs_source_location(dhsData.source_location_id);
                }
                
                console.log('DHS order created:');
                console.log('Reference:', dhsName);
                console.log('Location ID:', dhsData.source_location_id);
            }

            // Set partner from DHS data
            if (dhsData.partner_id) {
                const partner = this.pos.db.get_partner_by_id(dhsData.partner_id);
                if (partner) {
                    console.log('Setting partner on order:', partner);
                    order.set_partner(partner);
                    console.log('Partner set:', partner.name);
                }
            }

            // Add products to order
            let addedCount = 0;
            const missingProducts = [];
            console.log('Products to add:', dhsData.products);
            
            if (dhsData.products && Array.isArray(dhsData.products)) {
                for (const productData of dhsData.products) {
                    const product = this.pos.db.get_product_by_id(productData.product_id);
                    
                    console.log('Product data:', productData.product_id, productData.quantity, productData.price);
                    console.log('Processing product:', product);
                    
                    if (product) {
                        try {
                            const orderLine = order.add_product(product, {
                                quantity: productData.quantity || 1,
                                price: productData.price || product.lst_price,
                            });
                            
                            if (orderLine) {
                                addedCount++;
                                console.log(`Product added successfully. Total added: ${addedCount}`);
                            }
                        } catch (addError) {
                            console.error('Error adding product:', addError);
                            missingProducts.push(productData.name || `Product ID: ${productData.product_id}`);
                        }
                    } else {
                        console.warn(`Product not found in POS database: ${productData.name} (ID: ${productData.product_id})`);
                        missingProducts.push(productData.name || `Product ID: ${productData.product_id}`);
                    }
                }
            }

            // Show appropriate notification
            if (addedCount > 0) {
                let message = _t('Added %s products from DHS %s', addedCount, dhsData.dhs_name);
                
                if (useScanCardMode) {
                    message += _t(' (Live Stock Mode)');
                }
                
                if (missingProducts.length > 0) {
                    message += _t('\nSome products could not be added: %s', missingProducts.join(', '));
                    this.notification.add(message, { type: 'warning' });
                } else {
                    this.notification.add(message, { type: 'success' });
                }
                
            } else {
                let message = _t('No products could be added from DHS %s', dhsData.dhs_name);
                if (useScanCardMode) {
                    message += _t(' (Live Stock Mode)');
                }
                this.notification.add(message, { type: 'warning' });
            }

        } catch (error) {
            console.error('fetchAndAddDHSProducts failed:', error);
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: error.message || _t('Failed to process DHS products'),
            });
        }
    }
}

ProductScreen.addControlButton({
    component: CustomScanCard,
});