/** @odoo-module **/

import {ProductScreen} from "@point_of_sale/app/screens/product_screen/product_screen";
import {useService} from "@web/core/utils/hooks";
import {Component} from "@odoo/owl";
import {PayForDonation} from "@ah_advance_donation/PayForDonation/PayForDonation";


export class AdvanceDonationButton extends Component {
    static template = "ah_advance_donation.AdvanceDonationButton";

    setup() {
        this.orm = useService("orm");
        this.popup = useService("popup");
    }

    async onClick() {
        await this.orm.call('ah.advance.donation', "check_bank_ids")
            .then((data) => {
                if (data.status === 'error') {
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: data.body,
                    });
                }
                if (data.status === 'success') {
                    this.popup.add(PayForDonation, {
                        bank_ids: data.bank_ids
                    });
                }
        });
    }
}


ProductScreen.addControlButton({
    component: AdvanceDonationButton,
});
