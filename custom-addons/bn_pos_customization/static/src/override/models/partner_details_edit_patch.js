/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_details_edit/partner_details_edit";
import { _t } from "@web/core/l10n/translation";

patch(PartnerDetailsEdit.prototype, {
    saveChanges() {
        const name = this.changes.name || (this.props.partner && this.props.partner.name);
        
        if (name) {
            // Same regex as backend: Only letters, spaces, dots, hyphens, and apostrophes
            const regex = /^[a-zA-Z\s\.\-\']+$/;
            
            if (!regex.test(name)) {
                this.env.services.notification.add(
                    _t("Customer Name cannot contain numbers or special characters. Only letters, spaces, dots, hyphens, and apostrophes are allowed."),
                    { type: "danger" }
                );
                return; // Stop the save process
            }
        }
        
        return super.saveChanges(...arguments);
    },
});