/** @odoo-module **/

import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

import {_t} from "@web/core/l10n/translation";


export class PaymentPopup extends AbstractAwaitablePopup {
    static template = "bn_pos_payment_method.PaymentPopup";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.report = useService("report");
        this.notification = useService("notification");
        
        this.title = `${this.props.title} Details` || "Payment Details";
        
        this.label = `${this.props.label} Number`;
        this.is_bank = this.props.is_bank;

        // A cheque return ("Settle Order" in POS Cheques) hands back the
        // bounced cheque itself: start from its details
        const returnCheque = (this.is_bank && this.pos.get_order().get_return_cheque()) || {};

        this.state = useState({
            bank_name: this.props.bank_name || returnCheque.bank_name || "",
            number: this.props.number || returnCheque.cheque_number || "",
            date: this.props.date || returnCheque.cheque_date || "",
            banks: [],
            selected_bank_id: null,
        });

        this.loadBanks();

        // Today's date
        const today = new Date();

        // Calculate 6 months ago (minimum allowed date)
        const sixMonthsAgo = new Date();
        sixMonthsAgo.setMonth(today.getMonth() - 6);

        // Max date should be last day of the current year
        const endOfYear = new Date(today.getFullYear(), 11, 31);

        // Convert to YYYY-MM-DD
        this.minDate = sixMonthsAgo.toISOString().split("T")[0];
        this.maxDate = endOfYear.toISOString().split("T")[0];
    }

    async processReturn(orderID) {
        try {
            // 1. Fetch the return data from backend (method we created earlier)
            const returnData = await this.orm.call('pos.order', 'get_bounced_cheque_for_return', [orderID]);
            
            const selectedOrder = this.pos.get_order();
            
            // 2. Add items as negative quantities (Refund)
            for (let line of returnData.lines) {
                const product = this.pos.db.get_product_by_id(line.product_id);
                if (product) {
                    selectedOrder.add_product(product, {
                        quantity: -line.qty,
                        price: line.price_unit,
                    });
                }
            }

            // 3. Set Partner so the return is linked to the correct donor
            if (returnData.partner_id) {
                const partner = this.pos.db.get_partner_by_id(returnData.partner_id);
                if (partner) {
                    selectedOrder.set_partner(partner);
                }
            }

            // 4. Link the original bounced cheque order ID (optional but good for tracking)
            selectedOrder.set_pos_cheque_order_id(orderID); 

            // 5. Notify the cashier and close the popup
            this.notification.add(
                `Return prepared. Please click Payment and select the "Cheque Return" method to enter the new cheque details.`,
                { type: 'info', sticky: true }
            );
            
            // Close the ChequePopup so they can go to the payment screen
            super.confirm();

        } catch (error) {
            console.error("Error preparing return:", error);
            this.notification.add(
                "Failed to prepare return for this cheque.",
                { type: 'danger' }
            );
        }
    }

    async loadBanks() {
        try {
            const banks = await this.orm.call("bank", "get_banks", []);
            this.state.banks = banks;
            // Save a local copy for offline use
            try {
                localStorage.setItem("pos_bank_list", JSON.stringify(banks));
            } catch (e) {
                // ignore storage quota errors
            }
        } catch (error) {
            // Offline or request failed — fall back to the last saved list
            const cached = localStorage.getItem("pos_bank_list");
            if (cached) {
                this.state.banks = JSON.parse(cached);
                this.notification.add(
                    _t("You're offline — showing the last saved bank list."),
                    { type: "warning" }
                );
            } else {
                this.notification.add(
                    _t("Failed to load banks and no offline copy is available."),
                    { type: "danger" }
                );
            }
        }
    }

    // updateBankName(event) {
    //     this.state.bank_name = event.target.value;
    // }

    updateBank(event) {
        const bankId = parseInt(event.target.value);
        const bank = this.state.banks.find(b => b.id === bankId);

        this.state.selected_bank_id = bankId;
        this.state.bank_name = bank ? bank.name : "";
    }
    
    updateNumber(event) {
        this.state.number = event.target.value;
    }

    updateDate(event) {
        this.state.date = event.target.value;
    }

    canCancel() {
        return true;
    }

    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
    }

    async confirm() {
        // Validation: all visible fields must be filled
        if (this.is_bank) {
            if (!this.state.bank_name || !this.state.number || !this.state.date) {
                this.notification.add(_t("Please fill Bank Name, Cheque Number, and Date."), { type: "danger" });
                return;
            }
        } else {
            if (!this.state.number || !this.state.date) {
                this.notification.add(_t("Please fill QR Code Number and Date."), { type: "danger" });
                return;
            }
        }

        this.pos.addedOtherInfo = true;
        const selectedOrder = this.pos.get_order();
        if (this.is_bank) {
            selectedOrder.set_bank_name(this.state.bank_name);
            selectedOrder.set_cheque_number(this.state.number);
            selectedOrder.set_cheque_date(this.state.date);
        } else {
            selectedOrder.set_qr_code(this.state.number);
            selectedOrder.set_cheque_date(this.state.date);
        }
        this.props.close();
    }

    close() {
        this.props.close();
    }
}