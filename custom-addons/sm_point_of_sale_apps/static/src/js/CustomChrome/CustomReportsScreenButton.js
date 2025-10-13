/** @odoo-module */
import { Component } from "@odoo/owl";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
export class CustomReportsScreenButton extends Component {
    static template = "sm_point_of_sale_apps.CustomReportsScreenButton";
    setup() {
        this.pos = usePos();
    }
    async CustomReportsClick() {
        this.pos.showScreen("CustomReportsScreen");
    }
}
ProductScreen.addControlButton({
    component: CustomReportsScreenButton,
    condition: function () {
        return true;
    },
});