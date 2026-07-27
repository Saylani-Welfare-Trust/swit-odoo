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
        this.report = useService("report");    this.fetchCaseNumber();
        this.notification = useService("notification");
        this.fetchCaseNumber();
        this.title = this.props.title || "Provisional Order Details";
        
        this.donor_id = this.props.donor_id;
        this.bank_id = this.props.bank_id;
        this.donor_name = this.props.donor_name;
        this.orderLines = this.props.orderLines;
        this.favor = this.props.favor;
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
            selected_bank_id: false,
            case_no: "",  
        });

        // NEW: for Direct Deposit, pull the request no automatically from the order
        // that was set earlier by the Microfinance ('mf') or Medical Equipment ('me') flow.
        if (this.action_type === 'dd') {
            this.populateSourceRequestFromOrder();
        }
    }

    /**
     * NEW: Reads selectedOrder.extra_data (set earlier by the mf/me flows)
     * and fills the readonly source_request_type / source_request_no fields
     * shown on the Direct Deposit popup.
     */
    populateSourceRequestFromOrder() {
        const selectedOrder = this.pos.get_order();
        const extraData = selectedOrder && selectedOrder.extra_data;
        console.log("DD popup - extra_data:", extraData); // TEMP DEBUG

        if (!extraData) {
            console.log("DD popup - no extra_data on order"); // TEMP DEBUG
            return;
        }

        // NOTE: the scanned/selected record on the POS main screen stores its
        // reference under `record_number`, not `microfinance_request_no` /
        // `medical_equipment_request_no` (those only exist on the payload built
        // when confirming this popup directly in mf/me mode). Check both so this
        // works regardless of which path populated extra_data.
        const mf = extraData.microfinance;
        const me = extraData.medical_equipment;
        const mfRequestNo = mf && (mf.record_number || mf.microfinance_request_no);
        const meRequestNo = me && (me.record_number || me.medical_equipment_request_no);

        if (mfRequestNo) {
            this.state.source_request_type = 'Microfinance';
            this.state.source_request_no = mfRequestNo;
            // Keep amount in sync too, in case DD amount should follow the linked record
            if (mf.amount) {
                this.state.amount = parseFloat(mf.amount) || this.state.amount;
                this.state.total = this.state.amount + this.state.service_charges;
            }
            console.log("DD popup - matched microfinance:", this.state.source_request_no); // TEMP DEBUG
        } else if (meRequestNo) {
            this.state.source_request_type = 'Medical Equipment';
            this.state.source_request_no = meRequestNo;
            if (me.amount) {
                this.state.amount = parseFloat(me.amount) || this.state.amount;
                this.state.total = this.state.amount + this.state.service_charges;
            }
            console.log("DD popup - matched medical_equipment:", this.state.source_request_no); // TEMP DEBUG
        } else {
            console.log("DD popup - no matching request data found on order"); // TEMP DEBUG
        }
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

    onBankChange(ev) {
        const bankId = parseInt(ev.target.value) || null;
        this.state.selected_bank_id = bankId;
    }

    prepareOrderLines(orderLines) {
        return orderLines.map(line => (
                {
                    product_id: line.product.id,
                    quantity: line.quantity,
                    price: line.price,
                    qurbani_schedule: line.qurbani_schedule || null,
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

    async fetchCaseNumber() {
        // Only fetch for Direct Deposit
        if (this.action_type !== 'dd') {
            return;
        }

        try {
            let caseNo = "";
            
            // If we have donor_id, try to fetch from donor
            if (this.donor_id) {
                const result = await this.orm.searchRead(
                    'res.partner',
                    [['id', '=', this.donor_id]],
                    ['name', 'ref', 'display_name'],
                    { limit: 1 }
                );
                
                if (result && result.length > 0) {
                    // Priority: display_name > name > ref
                    caseNo = result[0].display_name || 
                            result[0].name || 
                            result[0].ref || 
                            "";
                }
            }
            
            // If no donor_id, try to get from props
            if (!caseNo && this.props.case_no) {
                caseNo = this.props.case_no;
            }
            
            // If still no case number, try from favor or other fields
            if (!caseNo && this.favor) {
                // You might want to fetch from favor record
                const favorResult = await this.orm.searchRead(
                    'donation.favor',  // or whatever your favor model is
                    [['name', '=', this.favor]],
                    ['name', 'display_name'],
                    { limit: 1 }
                );
                
                if (favorResult && favorResult.length > 0) {
                    caseNo = favorResult[0].display_name || favorResult[0].name;
                }
            }
            
            // Set the case number
            this.state.case_no = caseNo;
            
        } catch (error) {
            console.error("Error fetching case number:", error);
            // Don't show error to user for this non-critical field
            this.state.case_no = this.props.case_no || "N/A";
        }
    }
    async confirm(){
        const selectedOrder = this.pos.get_order();

        // Donation Home Service
        if (this.action_type === 'dhs') {
            const payload ={
                'donor_id': this.donor_id,
                'favor': this.favor,
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

            const data = await this.orm.call('medical.security.deposit', "get_medical_equipment_security_deposit", [payload]);
            
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

                    this.cancel();
                    return
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
                    quantity: record.quantity,
                    price_extra: record.amount,
                });
            }
               
            selectedOrder.set_receive_voucher(true)

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
               
            selectedOrder.set_receive_voucher(true)

            this.cancel()
        }

        // Direct Deposit
        if (this.action_type === 'dd') {
            const userId = this.pos.user ? this.pos.user.id : false;
            const payload ={
                'donor_id': this.donor_id,
                'favor': this.favor,
                'bank_id': this.state.selected_bank_id,
                'transaction_ref': this.state.transaction_ref,
                'service_charges': this.state.service_charges,
                'order_lines': this.prepareOrderLines(this.orderLines),
                'user_id': userId,
                'transfer_to_dhs': this.state.transfer_to_dhs,
                'address': this.state.address,
                // NEW: carry the linked request info through to the backend record
                'source_request_type': this.state.source_request_type,
                'source_request_no': this.state.source_request_no,
            }
    
            console.log("DD popup - payload sent:", payload); // TEMP DEBUG

            await this.orm.call('direct.deposit', "create_dd_record", [payload]).then((data) => {
                console.log("DD popup - response received:", data); // TEMP DEBUG

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
}