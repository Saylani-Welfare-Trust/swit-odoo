/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ChequePopup } from "../cheque_popup/cheque_popup";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    get checkChequeAccess(){
        // console.log(this);

        return this.pos._cheque || false;
    },

    async clickRecordCheque() {
        await this.popup.add(ChequePopup, {
            title: "POS Cheques",
            cancelText: "Cancel",
        });
    }
});