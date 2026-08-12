/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    get hasDonationInKind() {
        const orderlines = this.pos.get_order().get_orderlines();

        return orderlines.length > 0 && orderlines.every(line => {
            return !!line.product.is_donation_in_kind;
        });
    },
    
    async clickRecordDonationInKind() {
        const order = this.pos.get_order();

        const donor = order.partner ? order.partner : null;

        if (!donor) {
            return this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: "Please select a donor first..."
            });
        }

        if (!this.hasDonationInKind) {
            return this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: "Please select a valid product..."
            });
        }

        const donor_id = order.partner.id;
        const orderLines = order.get_orderlines();

        const payload = {
            'donor_id': donor_id,
            'order_lines': this.prepareOrderLines(orderLines),
        }

        await this.orm.call('donation.in.kind', "create_din_record", [payload]).then((data) => {
            if (data.status === 'error') {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: data.body,
                });
            }
            
            if (data.status === 'success') {
                order.set_source_document(data.origin)

                this.notification.add(_t("Operation Successful"), {
                    type: "info",
                });

                this.cancel()

                this.report.doAction("bn_donation_in_kind.action_report_donation_in_kind", [
                    data.id,
                ]);
            }
            this.pos.removeOrder(order);
            this.pos.add_new_order();
        })
    }
});