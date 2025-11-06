/** @odoo-module */

import { PartnerListScreen } from "@point_of_sale/app/screens/partner_list/partner_list";
import { patch } from "@web/core/utils/patch";

patch(PartnerListScreen.prototype, {
    get partners() {
        let res;
        if (this.state.query && this.state.query.trim() !== "") {
            res = this.pos.db.search_partner(this.state.query.trim());
        } else {
            res = this.pos.db.get_partners_sorted(5000);
        }

        // ✅ Filter partners that include 'Donor' in categories
        res = res.filter((partner) => {
            if (!partner.categories) return false;
            // normalize spacing and capitalization
            return partner.categories
                .split(",")
                .map((c) => c.trim().toLowerCase())
                .includes("donor".toLowerCase());
        });

        res.sort(function (a, b) {
            return (a.name || "").localeCompare(b.name || "");
        });
        // the selected partner (if any) is displayed at the top of the list
        if (this.state.selectedPartner) {
            const indexOfSelectedPartner = res.findIndex(
                (partner) => partner.id === this.state.selectedPartner.id
            );
            if (indexOfSelectedPartner !== -1) {
                res.splice(indexOfSelectedPartner, 1);
            }
            res.unshift(this.state.selectedPartner);
        }

        return res;
    }
});