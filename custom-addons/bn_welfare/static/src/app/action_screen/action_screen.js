/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    async clickRecordWF() {
        const { confirmed, payload: selectedOption } = await this.popup.add(
            SelectionPopup,
            {
                title: _t("Your Attention is Needed on a Disbursement Request!"),
                list: [
                    { id: "0", label: _t("One Time"), item: "one_time" },
                    { id: "1", label: _t("Recurring"), item: "recurring" },
                ],
            },
        );

        if (confirmed) {
            if (selectedOption === 'one_time') {
                this.popup.add(ReceivingPopup, {
                    title: "Disburement Number",
                    placeholder: "WF/XX/XXXXX",
                    action_type: "wf",
                    wf_request_type: "one_time"
                });
            } else {
                this.popup.add(ReceivingPopup, {
                    title: "Disburement Number",
                    placeholder: "WF/XX/XXXXX",
                    action_type: "wf",
                    wf_request_type: "recurring"
                });
            }
        }
    }
});