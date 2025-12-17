/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
const { DateTime } = luxon;

import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(Order.prototype, {
    export_for_printing() {
        return {
            ...super.export_for_printing(),
            
            partner: {
                name: this.partner ? this.partner.name : "",
                mobile: this.partner ? this.partner.mobile : "",
                phone: this.partner ? this.partner.phone : "",
            },
            branch_code: this.cashier.branch_code,
            branch_name: this.cashier.branch_name,
            receive_voucher: this.pos.receive_voucher
        };
    },

    async pay() {
        const order = this.pos.get_order();

        const donor = order.partner ? order.partner : null;

        if (!donor) {
            return this.env.services.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: "Please select a donor first..."
            });
        }
        
        await super.pay();
    },

    get_partner_mobile() {
        const partner = this.partner;
        return partner ? partner.mobile : "";
    },

    get_formatted_date(date) {
        return date
            ? DateTime.fromJSDate(this.date).toFormat("dd-MM-yyyy")
            : "";
    }
});