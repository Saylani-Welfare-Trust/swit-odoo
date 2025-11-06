/** @odoo-module **/

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from '@web/core/l10n/translation';
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import {ErrorPopup} from "@point_of_sale/app/errors/popups/error_popup";

export class DonationBoxPopup extends AbstractAwaitablePopup {
    static template = "bn_donation_box.DonationBoxPopup";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.report = useService("report");
        this.notification = useService("notification");

        // Props passed from python/rpc
        this.rider_ids = this.props.rider_ids || [];
        this.collection_ids = this.props.collection_ids || [];

        // Filtered collections
        this.rider_collections = [];
    }

    canCancel() {
        return true;
    }

    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
    }

    onSelection(ev) {
        const rider_id = parseInt(ev.target.value);
        this.rider_collections = this.collection_ids.filter(
            (col) => col.rider_id === rider_id
        );
        this.render(); // refresh template
    }

    async onClick(collection) {
        const payload = { 
            lot_id: collection.lot_id,
            box_no: collection.box_no,
            amount: collection.amount
        };

        await this.orm.call('key.issuance', "set_donation_amount", [payload]).then((data) => {
            if (data.status === 'error') {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: data.body,
                });
            } else if (data.status === 'success') {
                this.notification.add(_t("Amount Recorded Successfully"), {
                    type: "info",
                });
                this.report.doAction("bn_donation_box.donation_box_receipt_report_action", [data.id]);

                this.cancel();
            }
        });
    }
}
