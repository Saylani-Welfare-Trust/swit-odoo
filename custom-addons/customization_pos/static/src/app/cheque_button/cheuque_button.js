/**@odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { CustomButtonPopup } from "@customization_pos/app/button_popup/button_popup";


console.log(CustomButtonPopup);
export class CreateButton extends Component {
	    static template = "point_of_sale.CreateButton";
            
        setup() {
            
        this.pos = usePos();
            
        this.popup = useService("popup");
            
        }
            
        async onClick() {
            
        this.popup.add(CustomButtonPopup, {
                
        title: _t('Add Cheque'),
                        
        body: _t('Choose the alert type')
            
        })
            
        }
        }

ProductScreen.addControlButton({
component: CreateButton,
});
