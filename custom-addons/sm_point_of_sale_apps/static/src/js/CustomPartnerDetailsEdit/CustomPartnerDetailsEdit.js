/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

patch(PartnerDetailsEdit.prototype, {
    setup() {
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.pos = usePos();
        this.intFields = ["country_id", "state_id", "property_product_pricelist"];
        const partner = this.props.partner;
        this.changes = useState({
            state: partner.state,
            donor_type: partner.donor_type || "",
            // donor_type: partner.donor_type || "individual",
            is_donee: false,
            name: partner.name || "",
            phone_code_id: partner.name || "",
            street: partner.street || "",
            email: partner.email || "",
            phone: partner.phone || "",
            mobile: partner.mobile || "",
            cnic_no: partner.cnic_no || "",
            country_id: partner.country_id && partner.country_id[0],
            state_id: partner.state_id && partner.state_id[0],
            city: partner.city || "",
            zip: partner.zip || "",
            vat: partner.vat || "",
            donation_type : partner.donation_type || "",
            // amount : partner.amount || "",
            // bank_name : partner.bank_name || "",
            // cheque_number : partner.cheque_number || "",
            branch_id: partner.branch_id || "",
            registration_category: partner.registration_category || "",
            // delivery_charges_amount: partner.delivery_charges_amount || "",
            // donation_service: partner.donation_service || "",
            property_product_pricelist: this.setDefaultPricelist(partner),
        });
        this.partnerDetailsFields = {
            'street': _t('Address'),
            'email': _t('Email'),
            'phone': _t('Phone'),
            'phone_code_id': _t('Phone Code'),
            'mobile': _t('Mobile'),
            'cnic_no': _t('CNIC'),
            'country_id': _t('Country'),
            'state_id': _t('State_id'),
            'city': _t('City'),
            'vat': _t('Vat'),
            // 'amount': _t('Amount'),
            'bank_name': _t('Bank Name'),
            'cheque_number': _t('Cheque Number'),
            'branch_id': _t('branch_id'),
            'property_product_pricelist': _t('Pricelist'),
        };
        this.mobile_visibleCategories = [
            'walk_in_donor',
            'premium_individual_donor',
            'premium_corporate_donor',
            'online',
            'medical_patients',
            'medical_equipment',
            'donation_box',
        ];
        this.street_visibleCategories = [
            'donation_box',
            'donation_by_home',
        ];
        this.email_visibleCategories = [
            'premium_individual_donor',
            'premium_corporate_donor'
        ];
        this.phone_visibleCategories = [
            'premium_corporate_donor',
            'donation_by_home',
        ];
        this.cnicno_visibleCategories = [
            'premium_individual_donor',
            'medical_patients',
            'medical_equipment',
        ];
        this.donation_type_visibleCategories = [
            'donation_by_home',
        ];
        this.branch_id_visibleCategories = [
            'donation_by_home',
        ];
        this.delivery_charges_amount_visibleCategories = [
            'donation_by_home',
        ];
        Object.assign(this.props.imperativeHandle, {
            save: () => this.saveChanges(),
        });

        this.countries = useState({ list: [] });

        // Load countries from Odoo
        this.loadCountries();
    },
    get mobileFieldStyle() {
        return this.mobile_visibleCategories.includes(this.changes.donor_type) ? 'display: block;' : 'display: none;';
    },
    get phoneCodeFieldStyle() {
        return this.mobile_visibleCategories.includes(this.changes.phone_code_id) ? 'display: block;' : 'display: none;';
    },
    get streetFieldStyle() {
        return this.street_visibleCategories.includes(this.changes.donor_type) ? 'display: block;' : 'display: none;';
    },
    get emailFieldStyle() {
        return this.email_visibleCategories.includes(this.changes.donor_type) ? 'display: block;' : 'display: none;';
    },
    get phoneFieldStyle() {
        return this.phone_visibleCategories.includes(this.changes.donor_type) ? 'display: block;' : 'display: none;';
    },
    get cnicnoFieldStyle() {
        return this.cnicno_visibleCategories.includes(this.changes.donor_type) ? 'display: block;' : 'display: none;';
    },
    get donation_typeFieldStyle() {
        return this.donation_type_visibleCategories.includes(this.changes.donor_type) ? 'display: block;' : 'display: none;';
    },
    get branch_idFieldStyle() {
        return this.branch_id_visibleCategories.includes(this.changes.donor_type) ? 'display: block;' : 'display: none;';
    },
    get delivery_charges_amountFieldStyle() {
        return this.delivery_charges_amount_visibleCategories.includes(this.changes.donor_type) ? 'display: block;' : 'display: none;';
    },
    get delivery_charges_DonationServiceStyle() {
        if (this.changes.donation_service != '') {
            return 'display: none;'
        }
        else {
            return 'display: inline;'
        }
    },
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
    handleDonationTypeChange(selectElement) {
        const amount_element = document.querySelector(`div[id='amount']`);
        const bank_name_element = document.querySelector(`div[id='bank_name']`);
        const cheque_number_element = document.querySelector(`div[id='cheque_number']`);
        const reference_number_element = document.querySelector(`div[id='reference_number']`);
        const street_element = document.querySelector(`div[id='street']`);
        const phone_element = document.querySelector(`div[id='phone']`);
        const phone_code_id_element = document.querySelector(`div[id='phone_code_id']`);
        const mobile_element = document.querySelector(`div[id='mobile']`);
        const branch_id_element = document.querySelector(`div[id='branch_id']`);
        const delivery_charges_amount_element = document.querySelector(`div[id='delivery_charges_amount']`);
        const category_selected_value = selectElement.changes.donor_type;
        if(category_selected_value == 'donation_by_home') {
            if (street_element) {
                street_element.style.display = 'block';
            }
            if (phone_element) {
                phone_element.style.display = 'block';
            }
            if (phone_code_id_element) {
                phone_code_id_element.style.display = 'none';
            }
            if (mobile_element) {
                mobile_element.style.display = 'none';
            }
            if (branch_id_element) {
                branch_id_element.style.display= 'block';
            }
            if (delivery_charges_amount_element) {
                delivery_charges_amount_element.style.display= 'block';
            }
            if (amount_element) {
                amount_element.style.display = 'none';
            }
            if (cheque_number_element) {
                cheque_number_element.style.display = 'none';
            }
            if (bank_name_element) {
                bank_name_element.style.display = 'none';
            }
            if (reference_number_element) {
                reference_number_element.style.display = 'none';
            }
            const donation_type_selected_value = selectElement.changes.donation_type;
            if(donation_type_selected_value == 'cash') {
                if(amount_element) {
                    amount_element.style.display = 'block';
                }
            }
            else if(donation_type_selected_value == 'cheque') {
                if(amount_element) {
                    amount_element.style.display = 'block';
                }
                if (cheque_number_element) {
                    cheque_number_element.style.display = 'block';
                }
                if (bank_name_element) {
                    bank_name_element.style.display = 'block';
                }
            }
            else if(donation_type_selected_value == 'in_kind') {
                if (reference_number_element) {
                    reference_number_element.style.display = 'block';
                }
            }
        }
        else {
            if (amount_element) {
                amount_element.style.display = 'none';
            }
            if (cheque_number_element) {
                cheque_number_element.style.display = 'none';
            }
            if (bank_name_element) {
                bank_name_element.style.display = 'none';
            }
            if (reference_number_element) {
                reference_number_element.style.display = 'none';
            }
        }
    },
    handleCategoryChange(selectElement) {
        const partnerDetailsFields = this.partnerDetailsFields;
        const selectedValue = selectElement.changes.donor_type;
        const selected_array = [
            { 'individual': ['name', 'phone_code_id', 'mobile', 'email'] },
            { 'coorporate': ['name', 'phone_code_id', 'mobile', 'email', 'cnic_no'] },
            // { 'walk_in_donor': ['name', 'mobile'] },
            // { 'premium_individual_donor': ['name', 'mobile', 'email', 'cnic_no'] },
            // { 'premium_corporate_donor': ['name', 'phone', 'email', 'mobile'] },
            // { 'online': ['name', 'mobile', 'email'] },
            // { 'student': [] },
            // { 'microfinance_loans': [] },
            // { 'employees': [] },
            // { 'medical_patients': ['name', 'mobile', 'cnic_no'] },
            // { 'medical_equipment': ['name', 'mobile', 'cnic_no'] },
            // { 'donation_box': ['name', 'street', 'mobile'] },
            // { 'donors_of_associated_companies': [] },
            // { 'donation_by_home': ['name', 'mobile' , 'donation_type'] }
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
    async clickSend() {
        var partner_processed_changes = {
            'is_donee': false,
            'donor_type': 'individual',
            'name': this.changes.name,
            'phone_code_id': this.changes.phone_code_id,
            'street': this.changes.street,
            'phone': this.changes.phone,
            'branch_id': this.changes.branch_id,
            // 'delivery_charges_amount': this.changes.delivery_charges_amount,
            'donation_type': this.changes.donation_type,
            'registration_category': this.changes.registration_category,
            // 'amount': this.changes.amount,
            // 'bank_name': this.changes.bank_name,
            // 'cheque_number': this.changes.cheque_number,
            'remark': this.changes.remark,
        }
        const donation_service_id = await this.orm.call("donation.by.home.service", "create_from_ui", [partner_processed_changes]);
        this.changes.donation_service = donation_service_id;
        if(donation_service_id) {
            const donation_service_element = document.querySelector('#donation_service');
            if(donation_service_element) {
                donation_service_element.style.display = 'none';
            }
            else {
                donation_service_element.style.display = 'block';
            }
        }
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
        processedChanges.registration_category = 'donor';
        processedChanges.is_donee = false;
        processedChanges.state = 'register';
        if (processedChanges.mobile) {
            const digits = processedChanges.mobile.replace(/\D/g, "");
            processedChanges.mobile = digits.slice(-10);
        }
        // Check if state_id matches with country_id
        if (
            processedChanges.state_id &&
            this.pos.states.find((state) => state.id === processedChanges.state_id)
                .country_id[0] !== processedChanges.country_id
        ) {
            processedChanges.state_id = false;
        }
    
        // Ensure that the name field is filled
        if ((!this.props.partner.name && !processedChanges.name) || processedChanges.name === "") {
            return this.popup.add(ErrorPopup, {
                title: _t("Validation Error"),
                body: _t("Donor Name Is Required"),
            });
        }
    
        console.log(JSON.stringify(processedChanges));
    
        // Ensure that the donor_type is provided
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
                ['is_donee', '=', false], 
                ['registration_category', '=', 'donor'],
                ['state', '=','register']);  // Use array with correct structure
        } else if (donor_type === 'coorporate') {
            domain.push('|', 
                ['mobile', '=', mobile], 
                ['cnic_no', '=', cnic_no], 
                ['is_donee', '=', false], 
                ['registration_category', '=', 'donor'],
                ['state', '=','register']); 
        }
    
        try {
            // Wait for the asynchronous ORM call to complete
            // const res_partner = await this.orm.call('res.partner', 'search_read', [domain, ['name', 'cnic_no', 'email']]);
            
            // console.log(res_partner);
    
            // // If a matching donor exists, show an error
            // if (res_partner && res_partner.length > 0 && res_partner[0].name == processedChanges.name) {
            //     return this.popup.add(ErrorPopup, {
            //         title: _t(`Validation Error`),
            //         body: _t(`A Donor with the same ${donor_type === 'coorporate' ? 'CNIC / Mobile No.' : 'Mobile No.'} already exists in the System`),
            //     });
            // } else if (processedChanges.cnic_no != res_partner[0].cnic_no || processedChanges.email != res_partner[0].email) {
            //     return this.popup.add(ErrorPopup, {
            //         title: _t(`Validation Error`),
            //         body: _t(`A Donor with the same ${donor_type === 'coorporate' ? 'CNIC / Mobile No.' : 'Mobile No.'} already exists in the System`),
            //     });
            // }

            const res_partner = await this.orm.call('res.partner', 'search', [domain]);
            
            console.log(res_partner);
    
            // If a matching donor exists, show an error
            if (res_partner && res_partner.length > 0) {
                return this.popup.add(ErrorPopup, {
                    title: _t(`Validation Error`),
                    body: _t(`A Donor with the same ${donor_type === 'coorporate' ? 'CNIC / Mobile No.' : 'Mobile No.'} already exists in the System`),
                });
            }
    
            // Set the ID of the processed changes (if available)
            processedChanges.id = this.props.partner.id || false;
            console.log("domain:", domain);
            // Save the processed changes
            this.props.saveChanges(processedChanges);
            console.log("Processed Changes:", processedChanges);
        } catch (error) {
            console.error('Error during res.partner search:', error);
            this.popup.add(ErrorPopup, {
                title: _t('An error occurred while checking for existing donors.'),
            });
        }
    }
});


