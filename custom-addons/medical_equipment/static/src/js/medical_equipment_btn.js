/** @odoo-module **/
// Customer cheuque_number button fn
import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { onMounted } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

// import ChequePopup from "@pos_customer_feedback/js/Chequepopup"
export class MedicalButton extends Component {
    static template = "point_of_sale.MedicalequipmentButton";
    setup() {
    
        this.pos = usePos();
        this.popup = useService("popup");
    }

    async onClick() {
        console.log("hunain shaikh");
        this.pos.showScreen("MedicalScreen");

    
    }
}
ProductScreen.addControlButton({
    component: MedicalButton,
});
