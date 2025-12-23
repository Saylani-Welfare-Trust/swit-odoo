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
        
        // Set title based on action type
        if (this.action_type === 'dd_update') {
            this.title = "Update Direct Deposit Record";
        } else {
            this.title = this.props.title || "Provisional Order Details";
        }
        
        this.state = useState({
            microfinance_request_no: '',
            amount: parseFloat(this.props.amount) || 0,
            service_charges: 0,
            total: parseFloat(this.props.amount) || 0,
            address: this.props.address || "",   
            transaction_ref: this.props.transaction_ref || "",
            
            // DD Update specific state
            dd_reference: '',
            dd_record: null,
            dd_step: 'search',  // 'search' or 'action'
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

    updateAddress(event) {
        this.state.address = event.target.value;
    }
    
    updateTransactionRef(event) {
        this.state.transaction_ref = event.target.value;
    }

    updateDDReference(event) {
        this.state.dd_reference = event.target.value;
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

        // Direct Deposit Update
        if (this.action_type === 'dd_update') {
            if (this.state.dd_step === 'search') {
                await this.searchDDRecord();
            } else if (this.state.dd_step === 'action') {
                // This is handled by action buttons, not confirm
            }
        }
    }

    /**
     * Search for DD record by reference
     */
    async searchDDRecord() {
        if (!this.state.dd_reference) {
            this.notification.add(
                _t("Please enter a Direct Deposit reference"),
                { type: 'warning' }
            );
            return;
        }

        const records = await this.orm.searchRead(
            'direct.deposit',
            [['name', '=', this.state.dd_reference.trim()]],
            ['id', 'name', 'state', 'donor_id', 'amount', 'dhs_ids'],
            { limit: 1 }
        );

        if (!records.length) {
            this.notification.add(
                _t("Record '%s' not found", this.state.dd_reference),
                { type: 'warning' }
            );
            return;
        }

        this.state.dd_record = records[0];
        this.state.dd_step = 'action';
    }

    /**
     * Get available actions for the DD record based on its state
     */
    getDDActions() {
        const record = this.state.dd_record;
        if (!record) return [];

        const actions = [];

        // If state is 'draft' - show Clear and Not Clear options
        if (record.state === 'draft') {
            actions.push({ id: 'action_clear', label: '✓ Clear', class: 'btn-success' });
            actions.push({ id: 'action_not_clear', label: '✗ Not Clear', class: 'btn-danger' });
        }

        // If state is 'clear' and no DHS records - show Transfer to DHS option
        if (record.state === 'clear' && (!record.dhs_ids || record.dhs_ids.length === 0)) {
            actions.push({ id: 'action_transfer_to_dhs', label: '→ Transfer to DHS', class: 'btn-primary' });
        }

        return actions;
    }

    /**
     * Get message when no actions available
     */
    getDDNoActionMessage() {
        const record = this.state.dd_record;
        if (!record) return '';

        if (record.state === 'not_clear') {
            return _t("This record is marked as 'Not Clear'. No further actions available.");
        } else if (record.state === 'transferred') {
            return _t("This record has already been transferred to DHS.");
        } else if (record.state === 'clear' && record.dhs_ids && record.dhs_ids.length > 0) {
            return _t("This record has already been transferred to DHS.");
        }
        return _t("No actions available for this record.");
    }

    /**
     * Execute DD action
     */
    async executeDDAction(action) {
        const recordId = this.state.dd_record.id;

        try {
            if (action === 'action_clear') {
                await this.orm.call('direct.deposit', 'action_clear', [[recordId]]);
                this.notification.add(
                    _t("Record marked as Clear successfully!"),
                    { type: 'success' }
                );
                // Close popup first, then print report
                this.cancel();
                // Print the Direct Deposit duplicate report
                try {
                    await this.report.doAction("bn_direct_deposit.report_direct_deposit_duplicate", [recordId]);
                } catch (reportError) {
                    console.warn("Report print error:", reportError);
                }
                return;
            } else if (action === 'action_not_clear') {
                await this.orm.call('direct.deposit', 'action_not_clear', [[recordId]]);
                this.notification.add(
                    _t("Record marked as Not Clear successfully!"),
                    { type: 'success' }
                );
            } else if (action === 'action_transfer_to_dhs') {
                await this.orm.call('direct.deposit', 'action_transfer_to_dhs', [[recordId]]);
                this.notification.add(
                    _t("Record transferred to DHS successfully!"),
                    { type: 'success' }
                );
            }

            this.cancel();
        } catch (error) {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: error.message || _t("An error occurred while processing the action.")
            });
        }
    }

    /**
     * Go back to search step
     */
    backToSearch() {
        this.state.dd_record = null;
        this.state.dd_step = 'search';
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