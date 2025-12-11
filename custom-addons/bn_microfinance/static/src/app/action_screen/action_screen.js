/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ProvisionalPopup } from "@bn_pos_custom_action/app/provisional_popup/provisional_popup";
import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    async clickRecordMF() {
        const { confirmed, payload: selectedOption } = await this.popup.add(
            SelectionPopup,
            {
                title: _t("Your Attention is Needed for a Microfinance Request!"),
                list: [
                    { id: "0", label: _t("Security Deposit"), item: "provisional_order" },
                    { id: "1", label: _t("Insallment Receipt"), item: "settle" },
                    { id: "2", label: _t("Microfinance Recovery"), item: "recovery" },
                ],
            },
        );

        if (confirmed) {
            if (selectedOption === 'provisional_order') {
                this.popup.add(ProvisionalPopup, {
                    title: 'Security Deposit Details',
                    action_type: "mf"
                });
            }
            if (selectedOption === 'recovery') {
                this.popup.add(ReceivingPopup, {
                    title: "Microfinance Recovery",
                    placeholder: "MF/XX/XX/XXXXX",
                    action_type: "mf recovery"
                });
            } 
            if (selectedOption === 'settle') {
                this.popup.add(ReceivingPopup, {
                    title: "Microfinance Installment",
                    placeholder: "MF/XX/XX/XXXXX",
                    action_type: "mf"
                });
            }
        }
    }
});