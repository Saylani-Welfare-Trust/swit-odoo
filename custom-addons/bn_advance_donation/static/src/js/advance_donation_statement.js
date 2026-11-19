/** @odoo-module */
import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { download } from "@web/core/network/download";

const MODEL = "advance.donation.statement.wizard";

// "42101-1234567-1" and "4210112345671" match the same CNIC
const compact = (s) => String(s || "").toLowerCase().replace(/[\s-]/g, "");


export class AdvanceDonationStatement extends Component {
    setup() {
        this.orm    = useService("orm");
        this.action = useService("action");
        this.ui     = useService("ui");

        this.state = useState({
            // No dates: the donor's whole history (opening balance 0)
            date_from: '',
            date_to:   '',
            donor_id:  false,
            donor:     null,
            lines:     [],
            opening_balance: 0,
            total_in:  0,
            total_out: 0,
            balance:   0,
            currency:  '',
            loading:   false,
            error:     null,
            search:    '',

            // -------- donor picker --------
            donor_query:   '',
            donor_results: [],
            donor_open:    false,
            donor_active:  -1,
            donor_loading: false,

            // -------- extra filters --------
            filter_type:        '',
            filter_beneficiary: '',
            amount_min:         '',
            amount_max:         '',

            // options derived from loaded data
            type_options:        [],
            beneficiary_options: [],

            // ui toggle
            show_more_filters:   false,
        });

        this._donorSeq = 0;
        this._dataSeq = 0;
        this._donorTimer = null;
        onWillUnmount(() => clearTimeout(this._donorTimer));
    }

    _resetStatement() {
        Object.assign(this.state, {
            lines: [], opening_balance: 0, total_in: 0, total_out: 0, balance: 0,
            type_options: [], beneficiary_options: [], error: null, loading: false,
        });
    }

    async _loadData() {
        const seq = ++this._dataSeq;
        if (!this.state.donor_id) {
            this._resetStatement();
            return;
        }
        this.state.loading = true;
        try {
            const data = await this.orm.call(MODEL, "get_statement_data", [], {
                date_from: this.state.date_from || false,
                date_to:   this.state.date_to   || false,
                donor_id:  this.state.donor_id,
            });
            if (seq !== this._dataSeq) {
                return; // a newer request is on its way
            }
            this.state.lines           = data.lines           || [];
            this.state.opening_balance = data.opening_balance || 0;
            this.state.total_in        = data.total_in        || 0;
            this.state.total_out       = data.total_out       || 0;
            this.state.balance         = data.balance         || 0;
            this.state.currency        = data.currency        || '';
            if (data.donor) {
                this.state.donor = data.donor;
            }
            this.state.error           = null;

            this._updateFilterOptions();
        } catch (e) {
            if (seq === this._dataSeq) {
                this.state.error = (e.data && e.data.message) || e.message || String(e);
            }
        } finally {
            if (seq === this._dataSeq) {
                this.state.loading = false;
            }
        }
    }

    _updateFilterOptions() {
        const uniq = (arr) => [...new Set(arr.filter(Boolean))].sort();
        this.state.type_options        = uniq(this.state.lines.map(l => l.type));
        this.state.beneficiary_options = uniq(this.state.lines.map(l => l.beneficiary));
    }

    onDateChange(ev) {
        this.state[ev.target.name] = ev.target.value;
        this._loadData();
    }

    clearDates() {
        this.state.date_from = '';
        this.state.date_to = '';
        this._loadData();
    }

    // ------------------------------------------------------------------
    //  Donor picker (search by name, mobile, CNIC, registration ID...)
    // ------------------------------------------------------------------
    async _searchDonors() {
        const seq = ++this._donorSeq;
        this.state.donor_loading = true;
        try {
            const results = await this.orm.call(MODEL, "search_donors", [], {
                term: this.state.donor_query,
                limit: 20,
            });
            if (seq === this._donorSeq) {
                this.state.donor_results = results;
                this.state.donor_active = results.length ? 0 : -1;
            }
        } finally {
            if (seq === this._donorSeq) {
                this.state.donor_loading = false;
            }
        }
    }

    onDonorFocus() {
        this.state.donor_open = true;
        if (!this.state.donor_results.length) {
            this._searchDonors();
        }
    }

    onDonorInput(ev) {
        this.state.donor_query = ev.target.value;
        this.state.donor_open = true;
        clearTimeout(this._donorTimer);
        this._donorTimer = setTimeout(() => this._searchDonors(), 250);
    }

    onDonorKeydown(ev) {
        const results = this.state.donor_results;
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            this.state.donor_open = true;
            if (results.length) {
                this.state.donor_active = (this.state.donor_active + 1) % results.length;
            }
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            if (results.length) {
                this.state.donor_active = (this.state.donor_active - 1 + results.length) % results.length;
            }
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            const donor = results[this.state.donor_active];
            if (this.state.donor_open && donor) {
                this.selectDonor(donor);
                ev.target.blur();
            }
        } else if (ev.key === "Escape") {
            this.state.donor_open = false;
            ev.target.blur();
        }
    }

    onDonorBlur() {
        this.state.donor_open = false;
        // keep the chosen donor's name in the box
        this.state.donor_query = this.state.donor ? this.state.donor.name : '';
    }

    selectDonor(donor) {
        this.state.donor_id = donor.id;
        this.state.donor = donor;
        this.state.donor_query = donor.name;
        this.state.donor_open = false;
        this.clearAllFilters();
        this._loadData();
    }

    clearDonor() {
        this.state.donor_id = false;
        this.state.donor = null;
        this.state.donor_query = '';
        this.state.donor_results = [];
        this.clearAllFilters();
        this._loadData();
    }

    // ------------------------------------------------------------------
    //  Search
    // ------------------------------------------------------------------
    onSearchInput(ev)  { this.state.search = ev.target.value; }
    onSearchKeydown(ev) {
        if (ev.key === "Escape") { this.clearSearch(); ev.target.blur(); }
    }
    clearSearch() { this.state.search = ""; }

    // ------------------------------------------------------------------
    //  Extra filter handlers
    // ------------------------------------------------------------------
    onFilterChange(ev) {
        const name = ev.target.name;
        this.state[name] = ev.target.value;
    }
    toggleMoreFilters() {
        this.state.show_more_filters = !this.state.show_more_filters;
    }
    clearExtraFilters() {
        this.state.filter_type        = '';
        this.state.filter_beneficiary = '';
        this.state.amount_min         = '';
        this.state.amount_max         = '';
    }
    clearAllFilters() {
        this.clearExtraFilters();
        this.state.search = '';
    }

    // ------------------------------------------------------------------
    //  Filter state getters
    // ------------------------------------------------------------------
    get extraFiltersCount() {
        let n = 0;
        if (this.state.filter_type)        n++;
        if (this.state.filter_beneficiary) n++;
        if (this.state.amount_min !== '' && !isNaN(parseFloat(this.state.amount_min))) n++;
        if (this.state.amount_max !== '' && !isNaN(parseFloat(this.state.amount_max))) n++;
        return n;
    }

    get hasActiveFilters() {
        return !!(this.state.search || this.extraFiltersCount);
    }

    // ------------------------------------------------------------------
    //  Filtered lines (all filters compose)
    // ------------------------------------------------------------------
    get filteredLines() {
        let rows = this.state.lines;

        // 1) Search: the line's texts and the donee's name / numbers
        const q = (this.state.search || "").trim().toLowerCase();
        if (q) {
            const qc = compact(q);
            rows = rows.filter((l) => {
                const hay = [
                    l.date, l.reference, l.partner, l.type,
                    l.purpose, l.beneficiary, l.description, l.search_text,
                ].map((v) => (v == null ? "" : String(v))).join(" ").toLowerCase();
                return hay.includes(q) || (qc && compact(hay).includes(qc));
            });
        }

        // 2) Type
        if (this.state.filter_type) {
            rows = rows.filter(l => (l.type || '') === this.state.filter_type);
        }

        // 3) Beneficiary
        if (this.state.filter_beneficiary) {
            rows = rows.filter(l => (l.beneficiary || '') === this.state.filter_beneficiary);
        }

        // 4) Amount range (transaction size = in + out)
        const min = parseFloat(this.state.amount_min);
        const max = parseFloat(this.state.amount_max);
        if (!isNaN(min)) {
            rows = rows.filter(l => (Number(l.amount_in || 0) + Number(l.amount_out || 0)) >= min);
        }
        if (!isNaN(max)) {
            rows = rows.filter(l => (Number(l.amount_in || 0) + Number(l.amount_out || 0)) <= max);
        }

        return rows;
    }

    /** In / Out of the listed lines. The balance is always the donor's
     *  real closing balance: a filter hides lines, it does not undo them. */
    get filteredTotals() {
        if (!this.hasActiveFilters) {
            return {
                in:      this.state.total_in,
                out:     this.state.total_out,
                balance: this.state.balance,
            };
        }
        let tin = 0, tout = 0;
        for (const l of this.filteredLines) {
            tin  += Number(l.amount_in  || 0);
            tout += Number(l.amount_out || 0);
        }
        return { in: tin, out: tout, balance: this.state.balance };
    }

    get periodLabel() {
        const { date_from, date_to } = this.state;
        if (date_from && date_to) return `From ${date_from} to ${date_to}`;
        if (date_from) return `From ${date_from}`;
        if (date_to) return `Up to ${date_to}`;
        return "All transactions";
    }

    // ------------------------------------------------------------------
    //  Formatting
    // ------------------------------------------------------------------
    formatAmount(v) {
        const n = Number(v || 0);
        return n.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    // ------------------------------------------------------------------
    //  Print (PDF)
    // ------------------------------------------------------------------
    async printPdf() {
        if (!this.state.donor_id) {
            return;
        }
        const name = this.props.action.display_name || "Advance Donation Statement";
        return this.action.doAction({
            type: "ir.actions.report",
            report_type: "qweb-pdf",
            report_name: "bn_advance_donation.advance_donation_statement_report",
            report_file: "bn_advance_donation.advance_donation_statement_report",
            name,
            display_name: name,
            data: this._buildReportPayload(),
        });
    }

    // ------------------------------------------------------------------
    //  Export (XLSX)
    // ------------------------------------------------------------------
    async printXlsx() {
        if (!this.state.donor_id) {
            return;
        }
        const payload = {
            model: MODEL,
            data: JSON.stringify(this._buildReportPayload()),
            output_format: "xlsx",
            report_action: this.props.action.xml_id || "bn_advance_donation.action_advance_donation_statement",
            report_name: this.props.action.display_name || "Advance Donation Statement",
        };
        this.ui.block();
        try {
            await download({ url: "/xlsx_report", data: payload });
        } finally {
            this.ui.unblock();
        }
    }

    _buildReportPayload() {
        const totals = this.filteredTotals;
        return {
            lines: this.filteredLines,
            search: this.state.search || "",
            currency: this.state.currency || "",
            date_from: this.state.date_from,
            date_to: this.state.date_to,
            period_label: this.periodLabel,
            donor_id: this.state.donor_id || false,
            donor_name: this.state.donor ? this.state.donor.name : "",
            donor_details: this.state.donor ? this.state.donor.details : "",
            opening_balance: this.state.opening_balance,
            total_in: totals.in,
            total_out: totals.out,
            balance: totals.balance,
            all_lines_count: this.state.lines.length,
            filtered_lines_count: this.filteredLines.length,
            // active filters snapshot for the report header
            filter_type:        this.state.filter_type || "",
            filter_beneficiary: this.state.filter_beneficiary || "",
            amount_min:         this.state.amount_min || "",
            amount_max:         this.state.amount_max || "",
            report_name: this.props.action.display_name || "Advance Donation Statement",
        };
    }
}

AdvanceDonationStatement.template = "bn_advance_donation.AdvanceDonationStatement";

registry.category("actions").add(
    "advance_donation_statement",
    AdvanceDonationStatement
);
