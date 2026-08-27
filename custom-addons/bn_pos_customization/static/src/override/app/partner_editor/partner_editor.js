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

        // Validate state/country
        if (processedChanges.state_id) {
            const state = this.pos.states.find(
                (state) => state.id === processedChanges.state_id
            );

            if (
                state &&
                state.country_id &&
                state.country_id[0] !== processedChanges.country_id
            ) {
                processedChanges.state_id = false;
            }
        }

        // Donor name validation
        if (
            (!this.props.partner.name && !processedChanges.name) ||
            processedChanges.name === ""
        ) {
            return this.popup.add(ErrorPopup, {
                title: _t("A Donor Name Is Required"),
            });
        }

        // Donor type validation
        if (processedChanges.donor_type == null) {
            return this.popup.add(ErrorPopup, {
                title: _t("Validation Error"),
                body: _t("Donor Type Is Required"),
            });
        }

        const donor_type = processedChanges.donor_type;

        const mobile = processedChanges.mobile
            ? processedChanges.mobile.toString().trim()
            : '';

        const cnic_no = processedChanges.cnic_no
            ? processedChanges.cnic_no.toString().trim()
            : '';

        /*
        * OFFLINE DUPLICATE VALIDATION
        *
        * Do NOT use:
        * this.orm.call(...)
        *
        * Do NOT use:
        * this.pos.models
        *
        * Use the records already loaded into the POS.
        */
        const partnerModel = this.pos.data?.models?.["res.partner"];

        const partners = partnerModel
            ? partnerModel.getAll()
            : [];

        /**
         * Helper to get category names.
         *
         * Depending on the POS model definition, category_id can contain:
         *
         * [categoryId, categoryName]
         *
         * or relational records.
         */
        const getCategoryNames = (partner) => {
            const categories = partner.category_id || [];

            return categories.map((category) => {
                if (Array.isArray(category)) {
                    return category[1];
                }

                return category.name || "";
            });
        };

        let duplicatePartner = false;

        if (donor_type === "individual") {

            duplicatePartner = partners.find((partner) => {
                const partnerMobile = partner.mobile
                    ? partner.mobile.toString().trim()
                    : '';

                const categoryNames = getCategoryNames(partner);

                const isDonor = categoryNames.includes("Donor");
                const isIndividual = categoryNames.includes("Individual");

                return (
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
                    ? partner.mobile.toString().trim()
                    : '';

                const partnerCnic = partner.cnic_no
                    ? partner.cnic_no.toString().trim()
                    : '';

                const categoryNames = getCategoryNames(partner);

                const isDonor = categoryNames.includes("Donor");
                const isCorporate = categoryNames.includes(
                    "Coorporate / Institute"
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

        // Duplicate donor found
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

        // Save changes
        processedChanges.id = this.props.partner.id || false;

        this.props.saveChanges(processedChanges);
    }
})