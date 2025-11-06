/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { patch } from "@web/core/utils/patch";
import { DonationBoxPopup } from "../donation_box_popup/donation_box_popup";
import {ErrorPopup} from "@point_of_sale/app/errors/popups/error_popup";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    async clickRecordDonation() {
        const data = await this.orm.call('rider.collection', "get_rider_collection", []);

        console.log("Received Data:", data);

        // Check if data exists and has the required structure
        if (!data || typeof data !== 'object') {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("No data received from the server."),
            });
            return;
        }

        if (data.status === 'error') {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: data.body || _t("An unknown error occurred."),
            });
        } 
        else if (data.status === 'success') {
            // Check if collection and rider IDs exist before proceeding
            if (data.collection_ids && data.collection_ids.length > 0) {
                this.popup.add(DonationBoxPopup, {
                    collection_ids: data.collection_ids,
                    rider_ids: data.disbursement_ids || [],
                });
            } else {
                this.popup.add(ErrorPopup, {
                    title: _t("No Collections Found"),
                    body: _t("No collection data was received for this rider."),
                });
            }
        } 
        else {
            // Handle unexpected response
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("Unexpected response from the server."),
            });
        }
    }
});