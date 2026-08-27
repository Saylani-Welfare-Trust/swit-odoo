/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

patch(PartnerDetailsEdit.prototype, {
    async loadCountries() {
        try {
            const countries = await this.orm.searchRead(
                "res.country",
                [], // domain (all countries)
                ["id", "name", "phone_code"] // fields you need
            );
            this.countries.list = countries;
        } catch (error) {
            console.error("Error loading countries:", error);
        }
    },

    setup() {
        super.setup(...arguments);

        this.orm = useService("orm");

        this.changes.donor_type = ""
        this.changes.cnic_no = ""
        this.changes.country_code_id = ""

        this.countries = useState({ list: [] });

        // Load countries from Odoo
        this.loadCountries();

        this.partnerDetailsFields = {
            'email': _t('Email'),
            'country_code_id': _t('Country Code'),
            'mobile': _t('Mobile'),
            'cnic_no': _t('CNIC'),
        };
    },

    updateDonorType(event) {
        this.changes.donor_type = event.target.value;

        const partnerDetailsFields = this.partnerDetailsFields;
        const selectedValue = event.target.value;

        const selected_array = [
            { 'individual': ['name', 'country_code_id', 'mobile', 'email', 'cnic_no'] },
            { 'coorporate': ['name', 'country_code_id', 'mobile', 'email', 'cnic_no'] },
        ];

        const selectedFields = selected_array.find(item => item[selectedValue]);
        const fieldsToDisplay = selectedFields ? selectedFields[selectedValue] : [];
        
        Object.keys(partnerDetailsFields).forEach(field => {
            const element = document.querySelector(`div[id=${field}]`);
            if (element) {
                element.style.display = 'none';
            }
        });
        
        fieldsToDisplay.forEach(field => {
            if (partnerDetailsFields[field]) {
                const element = document.querySelector(`div[id=${field}]`);
                if (element) {
                    element.style.display = 'block';
                }
            }
        });
    },

    async saveChanges() {
        const processedChanges = {};

        for (const [key, value] of Object.entries(this.changes)) {
            if (this.intFields.includes(key)) {
                processedChanges[key] = parseInt(value) || false;
            } else {
                processedChanges[key] = value;
            }
        }

        // Mobile number length validation
        const mobile_no = processedChanges.mobile
            ? processedChanges.mobile.toString()
            : '';

        if (mobile_no && mobile_no.length !== 10) {
            return this.popup.add(ErrorPopup, {
                title: _t("Validation Error"),
                body: _t("Mobile number must be exactly 10 digits."),
            });
        }

        if (
            processedChanges.state_id &&
            this.pos.states.find((state) => state.id === processedChanges.state_id)
                .country_id[0] !== processedChanges.country_id
        ) {
            processedChanges.state_id = false;
        }

        if ((!this.props.partner.name && !processedChanges.name) || processedChanges.name === "") {
            return this.popup.add(ErrorPopup, {
                title: _t("A Donor Name Is Required"),
            });
        }

        if (processedChanges.donor_type == null) {
            return this.popup.add(ErrorPopup, {
                title: _t("Validation Error"),
                body: _t("Donor Type Is Required"),
            });
        }

        const donor_type = processedChanges.donor_type;
        const mobile = processedChanges.mobile
            ? processedChanges.mobile.toString()
            : '';
        const cnic_no = processedChanges.cnic_no
            ? processedChanges.cnic_no.toString()
            : '';

        /*
        * Offline duplicate donor validation
        *
        * Use partners already loaded in POS instead of ORM/RPC.
        */
        const partners = this.pos.models["res.partner"]?.getAll
            ? this.pos.models["res.partner"].getAll()
            : [];

        let duplicatePartner = false;

        if (donor_type === "individual") {
            duplicatePartner = partners.find((partner) => {
                const partnerMobile = partner.mobile
                    ? partner.mobile.toString()
                    : '';

                const isDonor = partner.category_id?.some(
                    (category) => category.name === "Donor"
                );

                const isIndividual = partner.category_id?.some(
                    (category) => category.name === "Individual"
                );

                return (
                    partnerMobile &&
                    mobile &&
                    partnerMobile === mobile &&
                    isDonor &&
                    isIndividual &&
                    partner.id !== this.props.partner.id
                );
            });
        } else if (donor_type === "coorporate") {
            duplicatePartner = partners.find((partner) => {
                const partnerMobile = partner.mobile
                    ? partner.mobile.toString()
                    : '';

                const partnerCnic = partner.cnic_no
                    ? partner.cnic_no.toString()
                    : '';

                const isDonor = partner.category_id?.some(
                    (category) => category.name === "Donor"
                );

                const isCorporate = partner.category_id?.some(
                    (category) => category.name === "Coorporate / Institute"
                );

                return (
                    isDonor &&
                    isCorporate &&
                    (
                        (mobile && partnerMobile === mobile) ||
                        (cnic_no && partnerCnic === cnic_no)
                    ) &&
                    partner.id !== this.props.partner.id
                );
            });
        }

        if (duplicatePartner) {
            return this.popup.add(ErrorPopup, {
                title: _t("Validation Error"),
                body: _t(
                    `A Donor with the same ${
                        donor_type === "coorporate"
                            ? "CNIC / Mobile No."
                            : "Mobile No."
                    } already exists in the System`
                ),
            });
        }

        processedChanges.id = this.props.partner.id || false;

        this.props.saveChanges(processedChanges);
    }
})