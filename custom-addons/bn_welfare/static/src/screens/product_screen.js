/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

// HOD welfare lines: the cashier may delete one (the rest of a welfare order
// can't be edited). The deleted lines are cancelled on the request once the
// order is paid (see payment_screen.js).
patch(ProductScreen.prototype, {
    getNumpadButtons() {
        const buttons = super.getNumpadButtons(...arguments);
        if (!this.pos.get_order()?.get_selected_orderline()?.welfare_hod_line_id) {
            return buttons;
        }
        return buttons.map((btn) => (btn.value === "Backspace" ? { ...btn, disabled: false } : btn));
    },

    // Backspace/Delete removes an HOD line in one press (by default the first
    // Backspace only sets the quantity to 0); nothing else edits it
    async updateSelectedOrderline({ buffer, key }) {
        const order = this.pos.get_order();
        const selectedLine = order?.get_selected_orderline();
        if (selectedLine?.welfare_hod_line_id) {
            this.numberBuffer.reset();
            if (["Backspace", "Delete"].includes(key)) {
                order.removeOrderline(selectedLine);
            }
            return;
        }
        return super.updateSelectedOrderline(...arguments);
    },
});
