/** @odoo-module */

import { PartnerListScreen } from "@point_of_sale/app/screens/partner_list/partner_list";
import { PartnerLine } from "@point_of_sale/app/screens/partner_list/partner_line/partner_line";
import { PosDB } from "@point_of_sale/app/store/db";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { PatientPopup } from "@bn_medical_pos/app/patient_popup/patient_popup";
import { isMedicalPatient } from "@bn_medical_pos/app/utils";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { sprintf } from "@web/core/utils/strings";
import { _t } from "@web/core/l10n/translation";

// On a Medical & Health POS the customer screen lists the patients instead of the donors,
// searches them on the server by name, mobile, CNIC or registration ID, and "Create" registers a patient.
patch(PartnerListScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.popup = useService("popup");
    },

    get isMedicalPos() {
        return Boolean(this.pos.config.is_medical_pos);
    },

    get partners() {
        if (!this.isMedicalPos) {
            return super.partners;
        }
        const query = (this.state.query || "").trim();
        const res = (query ? this.pos.db.search_partner(query) : this.pos.db.get_partners_sorted(1000))
            .filter(isMedicalPatient)
            .sort((a, b) => (a.name || "").localeCompare(b.name || ""));
        // the selected patient (if any) is displayed at the top of the list
        const selected = this.state.selectedPartner;
        if (selected) {
            const index = res.findIndex((partner) => partner.id === selected.id);
            if (index !== -1) {
                res.splice(index, 1);
            }
            res.unshift(selected);
        }
        return res;
    },

    async getNewPartners() {
        if (!this.isMedicalPos) {
            return super.getNewPartners(...arguments);
        }
        return await this.orm.silent.call("pos.session", "mh_search_patients", [
            [this.pos.pos_session.id],
            this.state.query || "",
            30,
            this.state.currentOffset,
        ]);
    },

    async createPartner() {
        if (!this.isMedicalPos) {
            return super.createPartner(...arguments);
        }
        const { confirmed, payload } = await this.popup.add(PatientPopup, {
            title: _t("Register Patient"),
            mode: "register",
            term: (this.state.query || "").trim(),
        });
        if (!confirmed || !payload?.partner) {
            return;
        }
        const { partner: partnerData, selected, existing } = payload;
        this.pos.addPartners([partnerData]);
        const partner = this.pos.db.get_partner_by_id(partnerData.id) || partnerData;
        if (!selected) {
            const regId = partnerData.primary_registration_id || "";
            this.notification.add(
                existing
                    ? sprintf(_t("%s (%s) is already a registered donee: tagged as patient."), partner.name, regId)
                    : sprintf(_t("Patient %s registered (%s)."), partner.name, regId),
                4000
            );
        }
        this.state.selectedPartner = partner;
        this.confirm();
    },
});

patch(PartnerLine.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();
    },
});

// Find patients (and donors) by CNIC, with or without dashes, and by registration ID in the local search
patch(PosDB.prototype, {
    _partner_search_string(partner) {
        const str = super._partner_search_string(...arguments);
        const cnic = partner.cnic_no || "";
        const extra = [cnic, cnic.replace(/\D/g, ""), partner.primary_registration_id || ""]
            .filter(Boolean)
            .join("|")
            .replace(/[:\n]/g, "");
        return extra ? str.replace(/\n$/, `|${extra}\n`) : str;
    },
});
