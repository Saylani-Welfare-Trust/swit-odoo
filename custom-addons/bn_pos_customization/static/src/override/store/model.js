/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    export_for_printing() {
        console.log(this);

        return {
            ...super.export_for_printing(),

            partner: {
                name: this.partner ? this.partner.name : "",
                mobile: this.partner ? this.partner.mobile : "",
                phone: this.partner ? this.partner.phone : "",
            }
        };
    },
});