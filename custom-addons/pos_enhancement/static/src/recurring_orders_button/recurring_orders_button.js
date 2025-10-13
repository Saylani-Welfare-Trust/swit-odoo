/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component } from "@odoo/owl";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class RecurringOrdersButton extends Component {
    static template = "pos_enhancement.RecurringOrdersButton";
    setup() {
        this.pos = usePos();
        this.popup=useService("popup");
    }
    async click() {
        // console.log("partner",this.pos.get_order())
        if (!this.pos.get_order().get_partner()) {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("Please select a donee first"),
            });
            return;
        }
        this.pos.showScreen("RecurringOrderScreen");
    }
}

ProductScreen.addControlButton({ component: RecurringOrdersButton
    
 });
