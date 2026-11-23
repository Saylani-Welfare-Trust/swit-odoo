/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { _t } from "@web/core/l10n/translation";
import { onMounted, useRef, useState } from "@odoo/owl";

/**
 * Approved prescriptions waiting for their bill.
 * Resolves with the prescription to bill.
 *
 * @props partner - only the prescriptions of this patient
 * @props prescriptions - already fetched prescriptions to start with
 * @props title
 */
export class PrescriptionListPopup extends AbstractAwaitablePopup {
    static template = "bn_medical_prescription.PrescriptionListPopup";
    // Enter runs the search instead of closing the popup
    static defaultProps = { confirmKey: false, cancelKey: "Escape" };

    setup() {
        super.setup();
        this.pos = usePos();
        // Own the numpad buffer while open, so keystrokes can't edit the order line underneath
        useService("number_buffer").use();

        this.searchInput = useRef("searchInput");
        this.searchRequest = 0;
        this.debouncedSearch = debounce(() => this.search(), 300);
        this.state = useState({
            term: "",
            prescriptions: this.props.prescriptions || [],
            searching: false,
            error: "",
            expanded: {},
        });

        onMounted(() => {
            this.searchInput.el?.focus();
            if (!this.props.prescriptions) {
                this.search();
            }
        });
    }

    get title() {
        if (this.props.title) {
            return this.props.title;
        }
        return _t("Prescriptions to Bill");
    }

    get loadedPrescriptionName() {
        return this.pos.get_order()?.medical_prescription_name || "";
    }

    async search() {
        const request = ++this.searchRequest;
        this.state.searching = true;
        this.state.error = "";
        try {
            const prescriptions = await this.pos.fetchMedicalPrescriptions({
                partnerId: this.props.partner?.id || false,
                term: this.state.term,
            });
            if (request === this.searchRequest) {
                this.state.prescriptions = prescriptions;
            }
        } catch (error) {
            if (request === this.searchRequest) {
                this.state.prescriptions = [];
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
            this.search();
        }
    }

    toggleLines(prescription) {
        this.state.expanded[prescription.id] = !this.state.expanded[prescription.id];
    }

    bill(prescription) {
        this.props.close({ confirmed: true, payload: prescription });
    }

    removeLoadedPrescription() {
        this.pos.removeMedicalPrescription();
        this.cancel();
    }

    formatCurrency(amount) {
        return this.env.utils.formatCurrency(amount);
    }

    errorMessage(error) {
        return error?.data?.message || error?.message || _t("Something went wrong, please try again.");
    }
}
