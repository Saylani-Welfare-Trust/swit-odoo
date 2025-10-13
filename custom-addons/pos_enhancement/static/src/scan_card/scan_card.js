/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class ScanCard extends Component {
    static template = "pos_enhancement.scan_card";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
    }
    async onClick() {
        const { confirmed, payload: barcode } = await this.popup.add(TextInputPopup, {
            startingValue: "",
            title: _t("Scan Card"),
        });

        if (confirmed) {
            let partner=this.pos.db.get_partner_by_barcode(barcode);
            let order=this.pos.get_order()
            order.set_partner(partner)
            console.log("partner", partner)
        }
    }
}

ProductScreen.addControlButton({
    component: ScanCard,
});
