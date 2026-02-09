/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ProvisionalPopup } from "@bn_pos_custom_action/app/provisional_popup/provisional_popup";
import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    get checkMedicalEquipmentAccess(){
        // console.log(this);

        return this.pos._medicalEquipment || false;
    },
    
    get checkMedicalEquipmentSettleOrderAccess(){
        // console.log(this);

        return this.pos._medicalEquipmentSettleOrder || false;
    },
    
    get checkMedicalEquipmentSecurityDepositAccess(){
        // console.log(this);

        return this.pos._medicalEquipmentSecurityDeposit || false;
    },

    async clickRecordME() {
        const { confirmed, payload: selectedOption } = await this.popup.add(
            SelectionPopup,
            this.checkMedicalEquipmentSettleOrderAccess && this.checkMedicalEquipmentSecurityDepositAccess
                ? {
                    title: _t("Your Attention is Needed for a Medical Equipment Request!"),
                    list: [
                        { id: "0", label: _t("Security Deposit"), item: "provisional_order" },
                        { id: "1", label: _t("Settle Order"), item: "settle" },
                    ],
                }
                :
                this.checkMedicalEquipmentSecurityDepositAccess 
                    ? {
                        title: _t("Your Attention is Needed for a Medical Equipment Request!"),
                        list: [
                            { id: "0", label: _t("Security Deposit"), item: "provisional_order" },
                        ],
                    }
                    :
                    this.checkMedicalEquipmentSettleOrderAccess 
                        ? {
                            title: _t("Your Attention is Needed for a Medical Equipment Request!"),
                            list: [
                                { id: "1", label: _t("Settle Order"), item: "settle" },
                            ],
                        }
                        : {}
        );

        if (confirmed) {
            if (selectedOption === 'provisional_order') {
                this.popup.add(ProvisionalPopup, {
                    title: 'Security Deposit Details',
                    action_type: "me"
                });
            }
            if (selectedOption === 'settle') {
                this.popup.add(ReceivingPopup, {
                    title: "Medical Equipment",
                    placeholder: "ME/XX/XXXXX",
                    action_type: "me"
                });
            }
        }
    }
});