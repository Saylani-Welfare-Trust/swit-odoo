/** @odoo-module **/
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";


patch(ProductScreen.prototype, {
    get checkProductPrice() {
        const orderLines = this.pos.get_order().get_orderlines(); // get current order lines

        console.log(orderLines);

        for (const line of orderLines) {
            if (line.product.lst_price > 0) {
                return true; // at least one line has price > 0
            }
        }
        return false; // no line has price > 0
    },
    
    get isWelfareOrder() {
        const order = this.pos.get_order();
        return order && order.extra_data && order.extra_data.welfare;
    },
    getNumpadButtons() {
        const buttons = [
            { value: "1" },
            { value: "2" },
            { value: "3" },
            { value: "quantity", text: _t("Qty") },
            { value: "4" },
            { value: "5" },
            { value: "6" },
            { value: "discount", text: _t("% Disc"), disabled: !this.pos.config.manual_discount },
            { value: "7" },
            { value: "8" },
            { value: "9" },
            {
                value: "price",
                text: _t("Price"),
                disabled: !this.pos.cashierHasPriceControlRights(),
            },
            { value: "-", text: "+/-" },
            { value: "0" },
            { value: this.env.services.localization.decimalPoint },
            { value: "Backspace", text: "⌫" },
            // Add your custom button here if needed, e.g.:
            // { value: "custom_action", text: _t("Custom"), custom: true },
        ];

        if (this.isWelfareOrder) {
            // Disable all except payment and custom action (adjust value as needed)
            return buttons.map(btn => {
                if (["payment", "custom_action"].includes(btn.value)) {
                    return { ...btn, disabled: false };
                }
                return { ...btn, disabled: true };
            });
        }
        return buttons.map((button) => ({
            ...button,
            class: this.pos.numpadMode === button.value ? "active border-primary" : "",
        }));
    }
})