/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { _t } from "@web/core/l10n/translation";
import { onMounted, useRef, useState } from "@odoo/owl";

/**
 * Search the registered patients (donees tagged Medical) or register a new one.
 * Resolves with { partner, selected } or { partner, existing } (partner in POS loader format).
 */
export class MedicalPatientPopup extends AbstractAwaitablePopup {
    static template = "bn_medical_equipment.MedicalPatientPopup";
    // Enter runs the search / submits the form instead of closing the popup
    static defaultProps = { confirmKey: false, cancelKey: "Escape" };

    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
        // Own the numpad buffer while open, so stray keystrokes can't edit the order line underneath
        useService("number_buffer").use();

        this.title = this.props.title || _t("Register Patient");
        // Odoo 17 exposes luxon as a global, not as an importable module
        this.today = luxon.DateTime.local().toISODate();
        this.searchInput = useRef("searchInput");
        this.searchRequest = 0;
        this.debouncedSearch = debounce(() => this.searchPatients(), 300);

        this.state = useState({
            mode: "search", // "search" | "register"
            term: "",
            patients: [],
            searching: false,
            saving: false,
            error: "",
            form: { name: "", mobile: "", cnic_no: "", date_of_birth: "" },
        });

        onMounted(() => {
            this.searchInput.el?.focus();
            this.searchPatients();
        });
    }

    async searchPatients() {
        const request = ++this.searchRequest;
        this.state.searching = true;
        this.state.error = "";
        try {
            const patients = await this.orm.call(
                "pos.session",
                "pos_search_medical_patients",
                [[this.pos.pos_session.id], this.state.term]
            );
            if (request === this.searchRequest) {
                this.state.patients = patients;
            }
        } catch (error) {
            if (request === this.searchRequest) {
                this.state.patients = [];
                this.state.error = this.errorMessage(error);
            }
        } finally {
            if (request === this.searchRequest) {
                this.state.searching = false;
            }
        }
    }

    onSearchKeydown(ev) {
        if (ev.key === "Enter") {
            this.searchPatients();
        }
    }

    selectPatient(patient) {
        this.props.close({ confirmed: true, payload: { partner: patient, selected: true } });
    }

    showRegisterForm() {
        // Carry over what was searched for
        const term = this.state.term.trim();
        const digits = term.replace(/\D/g, "");
        const form = this.state.form;
        if (digits.length === 13) {
            form.cnic_no = this.formatCnic(digits);
        } else if (digits.length === 10 || digits.length === 11) {
            form.mobile = this.cleanMobile(digits);
        } else if (term && !digits) {
            form.name = term;
        }
        this.state.error = "";
        this.state.mode = "register";
    }

    showSearch() {
        this.state.error = "";
        this.state.mode = "search";
    }

    onMobileInput(ev) {
        this.state.form.mobile = ev.target.value = this.cleanMobile(ev.target.value);
    }

    onCnicInput(ev) {
        this.state.form.cnic_no = ev.target.value = this.formatCnic(ev.target.value);
    }

    /** 10 digits, dropping the leading 0 of a number typed as 03XXXXXXXXX */
    cleanMobile(value) {
        let digits = value.replace(/\D/g, "");
        if (digits.length > 10 && digits.startsWith("0")) {
            digits = digits.slice(1);
        }
        return digits.slice(0, 10);
    }

    /** XXXXX-XXXXXXX-X, built up as it is typed */
    formatCnic(value) {
        const digits = value.replace(/\D/g, "").slice(0, 13);
        if (digits.length > 12) {
            return `${digits.slice(0, 5)}-${digits.slice(5, 12)}-${digits.slice(12)}`;
        }
        if (digits.length > 5) {
            return `${digits.slice(0, 5)}-${digits.slice(5)}`;
        }
        return digits;
    }

    validateForm(form) {
        if (!form.name.trim()) {
            return _t("Please enter the patient's name.");
        }
        if (!/^\d{10}$/.test(form.mobile)) {
            return _t("Contact number must contain exactly 10 digits.");
        }
        if (!/^\d{5}-\d{7}-\d$/.test(form.cnic_no)) {
            return _t("CNIC must be in the format XXXXX-XXXXXXX-X.");
        }
        if (!form.date_of_birth) {
            return _t("Please enter the date of birth.");
        }
        if (form.date_of_birth > this.today) {
            return _t("Date of birth cannot be in the future.");
        }
        return "";
    }

    async register() {
        if (this.state.saving) {
            return;
        }
        const form = this.state.form;
        const error = this.validateForm(form);
        if (error) {
            this.state.error = error;
            return;
        }
        this.state.saving = true;
        this.state.error = "";
        try {
            const result = await this.orm.call(
                "pos.session",
                "pos_register_medical_patient",
                [[this.pos.pos_session.id], { ...form, name: form.name.trim() }]
            );
            this.props.close({ confirmed: true, payload: result });
        } catch (error) {
            this.state.error = this.errorMessage(error);
            this.state.saving = false;
        }
    }

    errorMessage(error) {
        return error?.data?.message || error?.message || _t("Something went wrong, please try again.");
    }
}
