/** @odoo-module **/
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";


patch(ProductScreen.prototype, {
    get hasQurbaniProduct() {
        const currentOrder = this.pos.get_order();
        if (!currentOrder) return false;

        return currentOrder.get_orderlines().some(line => {
            const product = line.product;

            return (
                product.is_livestock &&
                product.detailed_type === "product" &&
                product.categ?.name?.toLowerCase().includes("qurbani")
            );
        });
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

        // 🔥 DISABLE ALL NUMPAD IF QURBANI PRODUCT EXISTS
        if (this.hasQurbaniProduct) {
            return buttons.map(btn => {
                if (btn.value === "Backspace") {
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