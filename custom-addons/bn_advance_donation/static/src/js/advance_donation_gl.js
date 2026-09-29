/** @odoo-module */
import { registry } from "@web/core/registry";
import { GeneralLedger } from "@dynamic_accounts_report/js/general_ledger";

/**
 * Advance-Donation General Ledger.
 *
 * Subclass of the shared General Ledger component. The only difference from
 * the standard GL is that ``advance_donation_only`` is forced to true so the
 * backend restricts the data to advance-donation journal entries.
 *
 * Registered under its own action tag ``adv_donation_gl`` so the standard
 * ``gen_l`` action is never affected.
 */
export class AdvanceDonationLedger extends GeneralLedger {
    setup() {
        super.setup(...arguments);

        // Force the flag — this is the whole point of the subclass.
        this.state.advance_donation_only = true;

        // super.setup() already triggered load_data() with the un-forced value,
        // so re-run it now that the flag is set.
        this.load_data();
    }
}

AdvanceDonationLedger.defaultProps = { resIds: [] };
AdvanceDonationLedger.template = "gl_template_new";

registry.category("actions").add("adv_donation_gl", AdvanceDonationLedger);