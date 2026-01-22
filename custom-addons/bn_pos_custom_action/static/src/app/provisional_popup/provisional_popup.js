/** @odoo-module **/

import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

import {_t} from "@web/core/l10n/translation";


export class ProvisionalPopup extends AbstractAwaitablePopup {
    static template = "bn_pos_custom_action.ProvisionalPopup";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.report = useService("report");
        this.notification = useService("notification");
        
        this.title = this.props.title || "Provisional Order Details";
        
        this.donor_id = this.props.donor_id;
        this.donor_name = this.props.donor_name;
        this.orderLines = this.props.orderLines;
        this.action_type = this.props.action_type;
        
        this.title = this.props.title || "Provisional Order Details";
        
        this.state = useState({
            microfinance_request_no: '',
            medical_equipment_request_no: '',
            amount: parseFloat(this.props.amount) || 0,
            service_charges: 0,
            total: parseFloat(this.props.amount) || 0,
            address: this.props.address || "",   
            transaction_ref: this.props.transaction_ref || "",
            transfer_to_dhs: false,
        });
    }

    saveServiceCharger(event) {
        const service_charges = parseFloat(event.target.value)
        this.state.service_charges = service_charges;
        this.state.total = this.state.amount + service_charges
    }

    updateMicrofinanceRequestNo(event) {
        this.state.microfinance_request_no = event.target.value;
    }

    updateMedicalEquipmentRequestNo(event) {
        this.state.medical_equipment_request_no = event.target.value;
    }

    updateAddress(event) {
        this.state.address = event.target.value;
    }
    
    updateTransactionRef(event) {
        this.state.transaction_ref = event.target.value;
    }

    updateTransferToDHS(event) {
        this.state.transfer_to_dhs = event.target.checked;
    }

    prepareOrderLines(orderLines) {
        return orderLines.map(line => (
                {
                    product_id: line.product.id,
                    quantity: line.quantity,
                    price: line.price,
                    remarks: line.customerNote
                }
            )
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

    async confirm(){
        const selectedOrder = this.pos.get_order();

        // Donation Home Service
        if (this.action_type === 'dhs') {
            console.log(this.orderLines);

            const payload ={
                'donor_id': this.donor_id,
                'address': this.state.address,
                'service_charges': this.state.service_charges,
                'order_lines': this.prepareOrderLines(this.orderLines),
            }
    
            await this.orm.call('donation.home.service', "create_dhs_record", [payload]).then((data) => {
                if (data.status === 'success') {
                    this.notification.add(_t("Operation Successful"), {
                        type: "info",
                    });
    
                    this.cancel()
                    
                    this.report.doAction("bn_donation_home_service.report_donation_home_service", [
                        data.id,
                    ]);
                }
    
                this.pos.removeOrder(selectedOrder);
                this.pos.add_new_order();
            })
        }

        // Medical Equipment
        if (this.action_type == 'me') {
            if (!this.state.medical_equipment_request_no) {
                this.notification.add(
                    "Please enter a Medical Equipment Request No.",
                    { type: 'warning' }
                );

                return;
            }

            const payload = {
                medical_equipment_request_no: this.state.medical_equipment_request_no,
                amount: this.state.amount,
                security_desposit: true
            }

            if (!selectedOrder.extra_data) {
                selectedOrder.extra_data = {};
            }

            selectedOrder.extra_data.medical_equipment = payload

            let record = null

            const data = await this.orm.call('medical.equipment', "get_medical_equipment_security_deposit", [payload]);
            
            if (data.status === 'error') {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: data.body,
                });
                return;
            }
            
            if (data.status === 'success') {
                record = data;
                payload.security_deposit_id = data.deposit_id || null;  // Will be null if deposit doesn't exist
                payload.medical_equipment_id = data.id;  // Store microfinance_id for creating record if needed
                payload.amount = data.amount;  // Store amount from microfinance request

                if (data.state === 'paid') {
                    this.notification.add(_t("Security deposit already paid"), {
                        type: "info",
                    });
                    
                    this.cancel();
                    return;
                }

                if (data.deposit_exists) {
                    this.notification.add(_t("Existing deposit found"), {
                        type: "info",
                    });
                } else {
                    this.notification.add(_t("Security deposit will be created upon payment"), {
                        type: "info",
                    });
                }
                
                // Set customer from donee_id
                if (data.donee_id) {
                    const partnerId = data.donee_id;
                    let partner = await this.getOrLoadPartner(partnerId);
                    if (partner) {
                        this.assignPartnerToOrder(partner, selectedOrder);
                    }
                }
            }
            // await this.orm.call('microfinance.installment', "create_microfinance_security_deposit", [payload]).then((data) => {
            //     if (data.status === 'error') {
            //         this.popup.add(ErrorPopup, {
            //             title: _t("Error"),
            //             body: data.body,
            //         });
            //     }
            //     else if (data.status === 'success') {
            //         record = data

            //         payload.security_deposit_id = data.deposit_id

            //         this.notification.add(_t("Operation Successful"), {
            //             type: "info",
            //         });
            //         // this.report.doAction("bn_microfinance.security_deposit_report_action", [
            //         //     data.id,
            //         // ]);
            //     }
            // });

            const securityProduct = await this.orm.searchRead(
                'product.product',
                [
                    ['name', '=', this.pos.company.medical_equipment_security_depsoit_product],
                    ['detailed_type', '=', 'service'],
                    ['available_in_pos', '=', true]
                ],
                ['id'],
                { limit: 1 }
            );
        
            if (securityProduct.length) {
                // Get the product from POS DB
                const product = this.pos.db.get_product_by_id(securityProduct[0].id);
                
                if (!product) {
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: _t(`${this.pos.company.medical_equipment_security_depsoit_product} product not loaded in POS session.`),
                    });
                    
                    return
                }
                
                // Add product to order
                selectedOrder.add_product(product, {
                    quantity: 1,
                    price_extra: record.amount,
                });
            }
               
            this.pos.receive_voucher = true

            this.cancel()
        }

        // Microfinance
        if (this.action_type == 'mf') {
            if (!this.state.microfinance_request_no) {
                this.notification.add(
                    "Please enter a Microfinance Request No.",
                    { type: 'warning' }
                );

                return;
            }

            const payload = {
                microfinance_request_no: this.state.microfinance_request_no,
                amount: this.state.amount,
                security_desposit: true
            }

            if (!selectedOrder.extra_data) {
                selectedOrder.extra_data = {};
            }

            selectedOrder.extra_data.microfinance = payload

            let record = null

            const data = await this.orm.call('microfinance.installment', "get_microfinance_security_deposit", [payload]);
            
            if (data.status === 'error') {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: data.body,
                });
                return;
            }
            
            if (data.status === 'success') {
                record = data;
                payload.security_deposit_id = data.deposit_id || null;  // Will be null if deposit doesn't exist
                payload.microfinance_id = data.id;  // Store microfinance_id for creating record if needed
                payload.amount = data.amount;  // Store amount from microfinance request

                if (data.state === 'paid') {
                    this.notification.add(_t("Security deposit already paid"), {
                        type: "info",
                    });
                    
                    this.cancel();
                    return;
                }

                if (data.deposit_exists) {
                    this.notification.add(_t("Existing deposit found"), {
                        type: "info",
                    });
                } else {
                    this.notification.add(_t("Security deposit will be created upon payment"), {
                        type: "info",
                    });
                }
                
                // Set customer from donee_id
                if (data.donee_id) {
                    const partnerId = data.donee_id;
                    let partner = await this.getOrLoadPartner(partnerId);
                    if (partner) {
                        this.assignPartnerToOrder(partner, selectedOrder);
                    }
                }
            }
            // await this.orm.call('microfinance.installment', "create_microfinance_security_deposit", [payload]).then((data) => {
            //     if (data.status === 'error') {
            //         this.popup.add(ErrorPopup, {
            //             title: _t("Error"),
            //             body: data.body,
            //         });
            //     }
            //     else if (data.status === 'success') {
            //         record = data

            //         payload.security_deposit_id = data.deposit_id

            //         this.notification.add(_t("Operation Successful"), {
            //             type: "info",
            //         });
            //         // this.report.doAction("bn_microfinance.security_deposit_report_action", [
            //         //     data.id,
            //         // ]);
            //     }
            // });

            // console.log('Hitting Provisional Popup');
            // console.log(this);

            const securityProduct = await this.orm.searchRead(
                'product.product',
                [
                    ['name', '=', this.pos.company.microfinance_security_depsoit_product],
                    ['detailed_type', '=', 'service'],
                    ['available_in_pos', '=', true]
                ],
                ['id'],
                { limit: 1 }
            );
        
            if (securityProduct.length) {
                // Get the product from POS DB
                const product = this.pos.db.get_product_by_id(securityProduct[0].id);
                
                if (!product) {
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: _t(`${this.pos.company.microfinance_security_depsoit_product} product not loaded in POS session.`),
                    });
                    
                    return
                }
                
                // Add product to order
                selectedOrder.add_product(product, {
                    quantity: 1,
                    price_extra: record.amount,
                });
            }
               
            this.pos.receive_voucher = true

            this.cancel()
        }

        // Direct Deposit
        if (this.action_type === 'dd') {
            const userId = this.pos.user ? this.pos.user.id : false;
            const payload ={
                'donor_id': this.donor_id,
                'transaction_ref': this.state.transaction_ref,
                'service_charges': this.state.service_charges,
                'order_lines': this.prepareOrderLines(this.orderLines),
                'user_id': userId,
                'transfer_to_dhs': this.state.transfer_to_dhs,
                'address': this.state.address,
                'service_charges': this.state.service_charges,
            }
    
            await this.orm.call('direct.deposit', "create_dd_record", [payload]).then((data) => {
                if (data.status === 'success') {
                    this.notification.add(_t("Operation Successful"), {
                        type: "info",
                    });
    
                    this.cancel()
                    
                    this.report.doAction("bn_direct_deposit.report_direct_deposit_provisional", [
                        data.id,
                    ]);
                }
    
                this.pos.removeOrder(selectedOrder);
                this.pos.add_new_order();
            })
        }
    }

    /**
     * Process partner assignment
     */
    async processPartner(record, selectedOrder) {
        if (this.action_type == 'mf') {
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
}