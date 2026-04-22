/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
const { DateTime } = luxon;

import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(Order.prototype, {
    export_for_printing() {
        const result = super.export_for_printing();

        return {
            ...result,

            partner: {
                name: this.partner ? this.partner.name : "",
                mobile: this.partner ? this.partner.mobile : "",
                phone: this.partner ? this.partner.phone : "",
                cnic_no: this.partner ? this.partner.cnic_no : "",
            },

            branch_code: this.cashier.branch_code,
            branch_name: this.cashier.branch_name,
            receive_voucher: this.pos.receive_voucher,
            // is_qurbani: this.pos.is_qurbani,
            is_bank: this.paymentlines[0]?.payment_method?.is_bank,
            is_donation_in_kind: this.paymentlines[0]?.payment_method?.is_donation_in_kind,

            // ✅ ADD THIS: enrich order lines
            orderlines: this.orderlines.map((line) => {
                const base = result.orderlines.find(
                    (l) => l.id === line.id || l.productName === line.product.display_name
                );

                return {
                    ...base,
                    qurbani_schedule_line: line.qurbani_schedule || null,
                    id: line.id,
                };
            }),
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