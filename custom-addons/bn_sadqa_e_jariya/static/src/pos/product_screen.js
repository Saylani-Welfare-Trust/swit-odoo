/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

patch(ProductScreen.prototype, {
    get isSadqaJariyaOrder() {
        return !!this.pos.get_order()?.extra_data?.sadqa_jariya;
    },

    // Sadqa e Jariya lines can't be edited, only HOD lines can be deleted
    getNumpadButtons() {
        const buttons = super.getNumpadButtons(...arguments);
        if (!this.isSadqaJariyaOrder) {
            return buttons;
        }
        const canDeleteLine = !!this.pos.get_order().get_selected_orderline()?.sadqa_jariya_hod_line_id;
        return buttons.map((button) => ({
            ...button,
            disabled: !(["payment", "custom_action"].includes(button.value) || (button.value === "Backspace" && canDeleteLine)),
        }));
    },

    // Backspace / Delete removes an HOD line in one press, nothing else is edited
    async updateSelectedOrderline({ buffer, key }) {
        if (!this.isSadqaJariyaOrder) {
            return super.updateSelectedOrderline(...arguments);
        }
        const order = this.pos.get_order();
        const selectedLine = order.get_selected_orderline();
        this.numberBuffer.reset();
        if (selectedLine?.sadqa_jariya_hod_line_id && ["Backspace", "Delete"].includes(key)) {
            order.removeOrderline(selectedLine);
        }
    },
});
