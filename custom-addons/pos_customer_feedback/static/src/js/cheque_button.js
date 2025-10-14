/** @odoo-module **/
// Customer cheuque_number button fn
import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { onMounted } from "@odoo/owl";

import ChequePopup from "@pos_customer_feedback/js/cheque_popup"
console.log("ChequePopup",ChequePopup);
// import ChequePopup from "@pos_customer_feedback/js/Chequepopup"
export class ChequesButton extends Component {
    static template = "point_of_sale.ChequesButton";
    setup() {
        const pos = useService("pos");
        if (!pos) {
            console.error("POS service not available");
            return;
        }
        this.pos=pos
         this.partner = pos.get_order().get_partner();
         this.selectedOrderline = pos.get_order().get_selected_orderline();

        const { popup } = this.env.services;
        this.popup = popup;

        onMounted(() => {
            
        }); 
    }

    

    async onClick() {
        
        const { confirmed, payload: inputFeedback } = await this.popup.add(
            ChequePopup, {
                startingValue: this.pos.get_order().get_comment_feedback(),
                title: _t('Cheque Order')
            }
        );
        if (confirmed) {
            
            this.pos.selectedOrder.comment_feedback = inputFeedback.commentValue;
            this.pos.selectedOrder.customer_feedback = inputFeedback.ratingValue;
            this.pos.selectedOrder.customer_feedback = inputFeedback.bankname;
            this.setStarRating(inputFeedback.ratingValue)
        }
    
    }
}
ProductScreen.addControlButton({
    component: ChequesButton,
});
