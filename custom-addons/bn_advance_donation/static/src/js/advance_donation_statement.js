/** @odoo-module */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { download } from "@web/core/network/download";
import { BlockUI } from "@web/core/ui/block_ui";


export class AdvanceDonationStatement extends Component {
    setup() {
        this.orm    = useService("orm");
        this.action = useService("action");

        const today = new Date();
        const firstOfYear = new Date(today.getFullYear(), 0, 1);

        this.state = useState({
            date_from: this._fmt(firstOfYear),
            date_to:   this._fmt(today),
            donor_id:  false,
            donors:    [],
            lines:     [],
            total_in:  0,
            total_out: 0,
            balance:   0,
            currency:  '',
            loading:   true,
            error:     null,
            search:    '',

            // -------- extra filters --------
            filter_type:        '',
            filter_purpose:     '',
            filter_beneficiary: '',
            filter_method:      '',
            amount_min:         '',
            amount_max:         '',

            // options derived from loaded data
            type_options:        [],
            purpose_options:     [],
            beneficiary_options: [],
            method_options:      [],

            // ui toggle
            show_more_filters:   false,
        });

        onWillStart(async () => {
            await this._loadDonors();
            await this._loadData();
        });
    }

    _fmt(d) {
        return d.toISOString().slice(0, 10);
    }

    async _loadDonors() {
        this.state.donors = await this.orm.searchRead(
            "res.partner",
            [["category_id.name", "=", "Donor"]],
            ["id", "name"],
            { limit: 500, order: "name" }
        );
    }

    async _loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "advance.donation.statement.wizard",
                "get_statement_data",
                [],
                {
                    date_from: this.state.date_from,
                    date_to:   this.state.date_to,
                    donor_id:  this.state.donor_id || false,
                }
            );
            this.state.lines     = data.lines     || [];
            this.state.total_in  = data.total_in  || 0;
            this.state.total_out = data.total_out || 0;
            this.state.balance   = data.balance   || 0;
            this.state.currency  = data.currency  || '';
            this.state.error     = null;

            this._updateFilterOptions();
        } catch (e) {
            this.state.error = e.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    _updateFilterOptions() {
        const uniq = (arr) => [...new Set(arr.filter(Boolean))].sort();
        this.state.type_options        = uniq(this.state.lines.map(l => l.type));
        this.state.purpose_options     = uniq(this.state.lines.map(l => l.purpose));
        this.state.beneficiary_options = uniq(this.state.lines.map(l => l.beneficiary));
        this.state.method_options      = uniq(this.state.lines.map(l => l.description));
    }

    onDateChange(ev) {
        this.state[ev.target.name] = ev.target.value;
        this._loadData();
    }

    onDonorChange(ev) {
        const v = ev.target.value;
        this.state.donor_id = v ? parseInt(v, 10) : false;
        this._loadData();
    }

    clearDonor() {
        this.state.donor_id = false;
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
        this.state.filter_purpose     = '';
        this.state.filter_beneficiary = '';
        this.state.filter_method      = '';
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
        if (this.state.filter_purpose)     n++;
        if (this.state.filter_beneficiary) n++;
        if (this.state.filter_method)      n++;
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

        // 1) Search
        const q = (this.state.search || "").trim().toLowerCase();
        if (q) {
            rows = rows.filter((l) => {
                const hay = [
                    l.date, l.reference, l.partner, l.type,
                    l.purpose, l.beneficiary, l.description,
                ].map((v) => (v == null ? "" : String(v))).join(" ").toLowerCase();
                return hay.includes(q);
            });
        }

        // 2) Type
        if (this.state.filter_type) {
            rows = rows.filter(l => (l.type || '') === this.state.filter_type);
        }

        // 3) Purpose
        if (this.state.filter_purpose) {
            rows = rows.filter(l => (l.purpose || '') === this.state.filter_purpose);
        }

        // 4) Beneficiary
        if (this.state.filter_beneficiary) {
            rows = rows.filter(l => (l.beneficiary || '') === this.state.filter_beneficiary);
        }

        // 5) Payment method (Description column)
        if (this.state.filter_method) {
            rows = rows.filter(l => (l.description || '') === this.state.filter_method);
        }

        // 6) Amount range (transaction size = in + out)
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
        return { in: tin, out: tout, balance: tin - tout };
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
        const self = this;
        return self.action.doAction({
            type: "ir.actions.report",
            report_type: "qweb-pdf",
            report_name: "bn_advance_donation.advance_donation_statement_report",
            report_file: "bn_advance_donation.advance_donation_statement_report",
            name: self.props.action.display_name || "Advance Donation Statement",
            display_name: self.props.action.display_name || "Advance Donation Statement",
            data: self._buildReportPayload(),
        });
    }

    // ------------------------------------------------------------------
    //  Export (XLSX)
    // ------------------------------------------------------------------
    async printXlsx() {
        const self = this;
        const payload = {
            model: "advance.donation.statement.wizard",
            data: JSON.stringify(self._buildReportPayload()),
            output_format: "xlsx",
            report_action: self.props.action.xml_id || "bn_advance_donation.action_advance_donation_statement",
            report_name: self.props.action.display_name || "Advance Donation Statement",
        };
        BlockUI;
        await download({
            url: "/xlsx_report",
            data: payload,
            complete: () => unblockUI,
            error: (err) => self.call("crash_manager", "rpc_error", err),
        });
    }

    _buildReportPayload() {
        const totals = this.filteredTotals;
        return {
            lines: this.filteredLines,
            search: this.state.search || "",
            currency: this.state.currency || "",
            date_from: this.state.date_from,
            date_to: this.state.date_to,
            donor_id: this.state.donor_id || false,
            donors: this.state.donors,
            total_in: totals.in,
            total_out: totals.out,
            balance: totals.balance,
            all_lines_count: this.state.lines.length,
            filtered_lines_count: this.filteredLines.length,
            // active filters snapshot for the report header
            filter_type:        this.state.filter_type || "",
            filter_purpose:     this.state.filter_purpose || "",
            filter_beneficiary: this.state.filter_beneficiary || "",
            filter_method:      this.state.filter_method || "",
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