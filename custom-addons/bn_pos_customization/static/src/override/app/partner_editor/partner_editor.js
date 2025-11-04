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

    get cnicStyle() {
        return this.changes.donor_type === 'individual' ? 'display: block;' : 'display: none;';
    },

    updateDonorType(event) {
        this.changes.donor_type = event.target.value;

        const partnerDetailsFields = this.partnerDetailsFields;
        const selectedValue = event.target.value;

        const selected_array = [
            { 'individual': ['name', 'country_code_id', 'mobile', 'email'] },
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

        const domain = [];
        const donor_type = processedChanges.donor_type;
        const mobile = processedChanges.mobile;
        const cnic_no = processedChanges.cnic_no;

        // Correct domain structure
        if (donor_type === 'individual') {
            domain.push(
                ['mobile', '=', mobile], 
                ['category_id.name', 'in', ['Donor']],
                ['category_id.name', 'in', ['Individual']],
                ['state', '=','register']);  // Use array with correct structure
        } else if (donor_type === 'coorporate') {
            domain.push('|', 
                ['mobile', '=', mobile], 
                ['cnic_no', '=', cnic_no], 
                ['category_id.name', 'in', ['Donor']],
                ['category_id.name', 'in', ['Coorporate / Institute']],
                ['state', '=','register']); 
        }

        const res_partner = await this.orm.call('res.partner', 'search', [domain]);

        if (res_partner && res_partner.length > 0) {
            return this.popup.add(ErrorPopup, {
                title: _t(`Validation Error`),
                body: _t(`A Donor with the same ${donor_type === 'coorporate' ? 'CNIC / Mobile No.' : 'Mobile No.'} already exists in the System`),
            });
        }

        processedChanges.id = this.props.partner.id || false;
        this.props.saveChanges(processedChanges);
    }
})