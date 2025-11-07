/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ProvisionalPopup } from "@bn_pos_custom_action/app/provisional_popup/provisional_popup";
import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    get checkLiveStock() {
        const orderlines = this.pos.get_order().get_orderlines();

        if (orderlines) {
            if (orderlines.length === 1) {
                const product = orderlines[0].get_product();
                
                return product && product.detailed_type !== 'service';
            }
            
            // Multiple lines
            return orderlines.some(line => {
                const product = line.get_product();
                return product && product.detailed_type !== 'service';
            });
        } else {
            return false;
        }
    },
    
    async clickRecordDHS() {
        const order = this.pos.get_order();

        const donor = order.partner ? order.partner : null;

        if (!donor) {
            return this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: "Please select a donor first..."
            });
        }

        const { confirmed, payload: selectedOption } = await this.popup.add(
            SelectionPopup,
            this.checkLiveStock
                ? {
                    title: _t("Let's create an order!"),
                    list: [
                        { id: "0", label: _t("Create an order"), item: "provisional_order" },
                    ],
                }
                : {
                    title: _t("Let's settle the provisional order!"),
                    list: [
                        { id: "0", label: _t("Settle the order"), item: "settle" },
                    ],
                }
        );

        if (confirmed) {
            const amount = order.get_total_with_tax();
            const orderLines = order.get_orderlines();

            if (selectedOption === 'provisional_order') {
                this.popup.add(ProvisionalPopup, {
                    donor_id: donor.id,
                    donor_name: donor.name,
                    donor_address: donor.address,
                    orderLines: orderLines,
                    amount: amount,
                    action_type: "dhs"
                });
            } else {
                this.popup.add(ReceivingPopup, {
                    title: "Donation Home Service",
                    placeholder: "DHS/XX/XXXXX",
                    action_type: "dhs"
                });
            }
        }
    }
});