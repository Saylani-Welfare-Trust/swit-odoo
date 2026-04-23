/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(Order.prototype, {
    export_for_printing() {
        const result = super.export_for_printing();

        return {
            ...result,

            is_qurbani: this.pos.is_qurbani,

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
});