/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { ActionScreen } from "../action_screen/action_screen";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class ActionButton extends Component {
    static template = "bn_pos_custom_action.ActionButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
    }

    // get selectedOrderline() {
    //     return this.pos.get_order().get_selected_orderline();
    // }

    async onClick() {
        // if (!this.selectedOrderline) {
        //     return;
        // }

        this.popup.add(ActionScreen);
    }
}

ProductScreen.addControlButton({
    component: ActionButton,
});
