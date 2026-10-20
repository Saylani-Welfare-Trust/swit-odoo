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
        
        this.state = useState({
            bank_name: this.props.bank_name || "",
            number: this.props.number || "",
            date: this.props.date || "",
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

    async loadBanks() {
        try {
            const banks = await this.orm.call(
                "bank",
                "get_banks",
                []
            );
            this.state.banks = banks;
        } catch (error) {
            this.notification.add(
                _t("Failed to load banks"),
                { type: "danger" }
            );
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