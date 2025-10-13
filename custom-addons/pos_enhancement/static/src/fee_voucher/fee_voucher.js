/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class FeeVoucher extends Component {
    static template = "pos_enhancement.fee_voucher";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
    }
    async onClick() {
        this.pos.showScreen("FeeVoucherManagementScreen");
    }
}

ProductScreen.addControlButton({
    component: FeeVoucher,
});
