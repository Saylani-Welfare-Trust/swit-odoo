/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PaymentPopup } from "../../app/payment_popup/payment_popup";
import {ErrorPopup} from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod) {
        if (paymentMethod.show_popup) {
            await this.popup.add(PaymentPopup, {
                title: paymentMethod.name,
                label: paymentMethod.name,
                is_bank: paymentMethod.is_bank,
                action_type: paymentMethod.name.toLowerCase()
            });
        }
        
        if (paymentMethod.is_donation_in_kind) {
            // console.log(this);
            const currentOrder = this.pos.get_order();

            currentOrder.donation_in_kind = true
        }

        if (this.pos.addedOtherInfo && paymentMethod.show_popup) {
            const res = super.addNewPaymentLine(...arguments);
        } else if (!paymentMethod.show_popup) {
            const res = super.addNewPaymentLine(...arguments);
        }
    },

    async validateOrder(isForceValidate) {
        const currentOrder = this.currentOrder;

        console.log('Hit New');
        console.log(currentOrder);

        if (currentOrder.donation_in_kind) {
            const donor_id = currentOrder.partner.id;
            const orderLines = currentOrder.get_orderlines();

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
                else if (data.status === 'success') {
                    this.notification.add(_t("Operation Successful"), {
                        type: "info",
                    });
                }
            })
        }

        // Continue with normal POS flow
        super.validateOrder(isForceValidate);
    },

    prepareOrderLines(orderLines) {
        return orderLines.map(line => (
                {
                    product_id: line.product.id,
                    quantity: line.quantity,
                    price: line.price,
                }
            )
        );
    }
})