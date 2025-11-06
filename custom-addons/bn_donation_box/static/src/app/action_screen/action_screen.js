/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { patch } from "@web/core/utils/patch";
import { DonationBoxPopup } from "../donation_box_popup/donation_box_popup";
import {ErrorPopup} from "@point_of_sale/app/errors/popups/error_popup";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    async clickRecordDonation() {
        await this.orm.call('rider.collection', "get_rider_collection", []).then((data) => {
            console.log(data);

            if (data.status === 'error') {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: data.body,
                });
            }
            else if (data.status === 'success') {
                this.popup.add(DonationBoxPopup, {
                    collection_ids: data.collection_ids,
                    rider_ids: data.disbursement_ids
                });
            }
        });
    }
});