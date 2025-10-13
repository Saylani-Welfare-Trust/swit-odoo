/** @odoo-module */
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useRef, onMounted, useState } from "@odoo/owl";

export class CustomChequeButtonPopup extends AbstractAwaitablePopup {
    static template = "custom_popup.CustomChequeButtonPopup";
    static defaultProps = {
       closePopup: _t("Cancel"),
       confirmText: _t("Save"),
       title: _t("Add Cheque"),
    };
    setup() {
        super.setup();
        this.pos = usePos();
        this.check_bank_name = '';
        this.check_cheque_number = '';
    }
    onCheckBankNameChange(event) {
        this.check_bank_name = event.target.value;
    }
    onChequeNumberrChange(event) {
        this.check_cheque_number = event.target.value;
    }
    async confirm() {
        const bankName = this.check_bank_name;
        const chequeNumber = this.check_cheque_number;
        const order = this.pos.get_order();
        if (order) {
            order.set_order_return_reason(chequeNumber);
        }
        this.cancel()
    }
    getPayload() {
        return {
            check_bank_name_value: this.check_bank_name,
            check_cheque_number_value: this.check_cheque_number,
        };
   }
}