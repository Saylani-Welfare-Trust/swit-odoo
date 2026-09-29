/** @odoo-module */
import { registry } from "@web/core/registry";
import { GeneralLedger } from "@dynamic_accounts_report/js/general_ledger";

/**
 * Advance-donation General Ledger.
 *
 * Subclass of the shared GL component. It forces ``advance_donation_only``
 * to true, so the backend filters the data down to advance-donation
 * journal entries only. Registered under its own action tag
 * ``adv_donation_gl`` so the standard ``gen_l`` action stays untouched.
 */
export class AdvanceDonationLedger extends GeneralLedger {
    setup() {
        super.setup(...arguments);
        // Force the flag regardless of what the action params contain.
        this.state.advance_donation_only = true;
        // Reload with the correct flag, because super.setup() already
        // fired load_data() with the un-forced value.
        this.load_data();
    }
}

AdvanceDonationLedger.defaultProps = { resIds: [] };
AdvanceDonationLedger.template = "gl_template_new";

registry.category("actions").add("adv_donation_gl", AdvanceDonationLedger);