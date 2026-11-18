/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ProvisionalPopup } from "@bn_pos_custom_action/app/provisional_popup/provisional_popup";
import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { MedicalPatientPopup } from "@bn_medical_equipment/app/medical_patient_popup/medical_patient_popup";
import { patch } from "@web/core/utils/patch";
import { sprintf } from "@web/core/utils/strings";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    get checkMedicalEquipmentAccess(){
        return this.pos._medicalEquipment || false;
    },

    get checkMedicalPatientAccess() {
        return this.pos._medicalPatientRegistration || false;
    },

    /** Find or register a patient (donee tagged Medical) and set them as the order's customer */
    async clickRegisterPatient() {
        const { confirmed, payload } = await this.popup.add(MedicalPatientPopup, {
            title: _t("Register Patient"),
        });
        if (!confirmed || !payload?.partner) {
            return;
        }

        const { partner: partnerData, selected, existing } = payload;
        this.pos.db.add_partners([partnerData]);
        const partner = this.pos.db.get_partner_by_id(partnerData.id) || partnerData;
        this.pos.get_order().set_partner(partner);

        const regId = partnerData.primary_registration_id || "";
        let message;
        if (selected) {
            message = sprintf(_t("Customer set to: %s"), partner.name);
        } else if (existing) {
            message = sprintf(_t("%s (%s) is already a registered donee: tagged as patient and set as customer."), partner.name, regId);
        } else {
            message = sprintf(_t("Patient %s registered (%s) and set as customer."), partner.name, regId);
        }
        this.notification.add(message, { type: existing ? "warning" : "success" });
        this.cancel();
    },
    
    get checkMedicalEquipmentSettleOrderAccess(){
        return this.pos._medicalEquipmentSettleOrder || false;
    },
    
    get checkMedicalEquipmentSecurityDepositAccess(){
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