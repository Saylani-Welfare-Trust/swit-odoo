/** @odoo-module */
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class CustomButtonPopup extends AbstractAwaitablePopup {
    static template = "customization_pos.CustomButtonPopup";

    static defaultProps = {
        closePopup: _t("Cancel"),
        confirmText: _t("Save"),
        title: _t("Customer Details"),
    };

    setup() {
        super.setup();
        this.pos = usePos();
        this.bankName = "";
        this.chequeNumber = "";
    }

    async save_button() {
        const bankName = this.bankName;
        const chequeNumber = this.chequeNumber;

        const order = this.pos.get_order();
        if (order) {
            order.set_order_return_reason(chequeNumber);
        }

        console.log("order",order)
        console.log("Cheque details saved:", 

            { bankName, chequeNumber });

        // Close the popup after saving
        this.cancel()
    }

    onBankNameInput(ev) {
        this.bankName = ev.target.value;
    }

    onChequeNumberInput(ev) {
        this.chequeNumber = ev.target.value;
    }
}
