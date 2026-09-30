/** @odoo-module */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


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
            search:    '',          // <-- search term (client side)
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
        } catch (e) {
            this.state.error = e.message || String(e);
        } finally {
            this.state.loading = false;
        }
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
    //  Search / filtering (client side, over the loaded lines)
    // ------------------------------------------------------------------
    get searchTerm() {
        return (this.state.search || "").trim().toLowerCase();
    }

    get isFiltered() {
        return this.searchTerm.length > 0;
    }

    /** Lines matching the current search term. */
    get filteredLines() {
        const q = this.searchTerm;
        if (!q) {
            return this.state.lines;
        }
        return this.state.lines.filter((l) => this._matches(l, q));
    }

    _matches(line, q) {
        const haystack = [
            line.date,
            line.reference,
            line.partner,
            line.type,
            line.purpose,
            line.beneficiary,
            line.description,
        ]
            .map((v) => (v === null || v === undefined ? "" : String(v)))
            .join(" ")
            .toLowerCase();
        return haystack.includes(q);
    }

    /** Totals: whole range when not filtered, displayed rows when filtered. */
    get totals() {
        if (!this.isFiltered) {
            return {
                in:      this.state.total_in,
                out:     this.state.total_out,
                balance: this.state.balance,
            };
        }
        let tin = 0;
        let tout = 0;
        for (const l of this.filteredLines) {
            tin  += Number(l.amount_in  || 0);
            tout += Number(l.amount_out || 0);
        }
        return { in: tin, out: tout, balance: tin - tout };
    }

    clearSearch() {
        this.state.search = "";
    }

    onSearchKeydown(ev) {
        if (ev.key === "Escape") {
            this.clearSearch();
            ev.target.blur();
        }
    }
    // ------------------------------------------------------------------

    formatAmount(v) {
        const n = Number(v || 0);
        return n.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    async printXlsx() {
        // Optional: hook up to an XLSX export later.
        console.log("XLSX export not implemented yet");
    }
}

AdvanceDonationStatement.template = "bn_advance_donation.AdvanceDonationStatement";

registry.category("actions").add(
    "advance_donation_statement",
    AdvanceDonationStatement
);