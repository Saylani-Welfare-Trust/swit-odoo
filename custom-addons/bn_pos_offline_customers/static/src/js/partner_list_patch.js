/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerListScreen } from "@point_of_sale/app/screens/partner_list/partner_list_screen";
import { searchCustomersLocal } from "./customer_offline_db";
import { _t } from "@web/core/l10n/translation";

// Falls back to the locally cached (IndexedDB) customer list whenever the
// live server search fails — typically because the POS is offline.
// Wraps the exact method Odoo calls when you type a name/phone and press
// Enter in the Customer screen, so this activates transparently without
// touching how the screen is normally used.
patch(PartnerListScreen.prototype, {
    async getNewPartners() {
        try {
            return await super.getNewPartners(...arguments);
        } catch (error) {
            console.warn(
                "[pos_offline_customers] Online customer search failed, " +
                    "falling back to offline cache:",
                error
            );

            const search =
                this.state && this.state.query ? this.state.query.trim() : "";
            if (!search) {
                return [];
            }

            const localResults = await searchCustomersLocal(search, 30);

            // Best-effort notification — depends on which service name your
            // Odoo build exposes on this component (notification / dialog).
            // Wrapped so a missing service never breaks the search itself.
            try {
                if (this.notification) {
                    this.notification.add(
                        _t("You're offline \u2014 showing cached customers only."),
                        { type: "warning" }
                    );
                }
            } catch (notifError) {
                // Ignore — surfacing results matters more than the toast.
            }

            // Shaped to look like a normal res.partner record. Fields we
            // don't cache (email, street, city, image, barcode) are set to
            // a safe falsy default so the customer list template doesn't
            // break on missing data. If your PartnerLine template needs a
            // different shape, share the console error and this mapping
            // gets adjusted.
            return localResults.map((c) => ({
                id: c.id,
                name: c.name || "",
                phone: c.phone || false,
                mobile: c.mobile || false,
                email: false,
                street: false,
                city: false,
                barcode: false,
                image_128: false,
                parent_name: false,
            }));
        }
    },
});
