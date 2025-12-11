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
        
        this.state = useState({
            microfinance_request_no: '',

            amount: parseFloat(this.props.amount),
            service_charges: 0,
            total: parseFloat(this.props.amount),
            donor_address: this.props.donor_address || "",            
        });
    }

    saveServiceCharger(event) {
        const service_charges = parseFloat(event.target.value)
        this.state.service_charges = service_charges;
        this.state.total = this.state.amount + service_charges
    }

    updateAddress(event) {
        this.state.donor_address = event.target.value;
    }

    updateMicrofinanceRequestNo(event) {
        this.state.microfinance_request_no = event.target.value;
    }

    prepareOrderLines(orderLines) {
        return orderLines.map(line => (
                {
                    product_id: line.product.id,
                    quantity: line.quantity,
                    price: line.price,
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
            const payload ={
                'donor_id': this.donor_id,
                'address': this.state.donor_address,
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

            await this.orm.call('microfinance.installment', "get_microfinance_security_deposit", [payload]).then((data) => {
                if (data.status === 'error') {
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: data.body,
                    });
                }
                else if (data.status === 'success') {
                    record = data

                    payload.security_deposit_id = data.deposit_id

                    this.notification.add(_t("Operation Successful"), {
                        type: "info",
                    });
                    // this.report.doAction("bn_microfinance.security_deposit_report_action", [
                    //     data.id,
                    // ]);
                }
            });
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
                    ['name', '=', 'Microfinance Security Deposit'],
                    ['type', '=', 'service'],
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
                        body: _t("Microfinance Security Deposit product not loaded in POS session."),
                    });
                    
                    return
                }
                
                // Add product to order
                selectedOrder.add_product(product, {
                    quantity: 1,
                    price_extra: record.amount,
                });
            }

            await this.processPartner(record, selectedOrder);
               
            this.pos.receive_voucher = true

            this.cancel()
        }

        // Donation Home Service
        if (this.action_type === 'dd') {
            const payload ={
                'donor_id': this.donor_id,
                'address': this.state.donor_address,
                'service_charges': this.state.service_charges,
                'order_lines': this.prepareOrderLines(this.orderLines),
            }
    
            await this.orm.call('direct.deposit', "create_dd_record", [payload]).then((data) => {
                if (data.status === 'success') {
                    this.notification.add(_t("Operation Successful"), {
                        type: "info",
                    });
    
                    this.cancel()
                    
                    this.report.doAction("bn_direct_deposit.report_direct_deposit", [
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