/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const currentOrder = this.currentOrder;

        let hasQurbaniProduct = false;
        let hasOtherCategoryProduct = false;

        // -------------------------
        // ✅ Check Order Lines
        // -------------------------
        for (let line of currentOrder.get_orderlines()) {
            const product = line.product;

            const isQurbaniLivestock =
                product.is_livestock &&
                product.detailed_type === "product" &&
                product.categ?.name?.toLowerCase().includes("qurbani");

            // -----------------------------------
            // Detect qurbani product
            // -----------------------------------
            if (isQurbaniLivestock) {
                hasQurbaniProduct = true;
            }

            // -----------------------------------
            // If product is NOT qurbani livestock
            // -----------------------------------
            if (!isQurbaniLivestock) {
                hasOtherCategoryProduct = true;
            }
        }

        // ------------------------------------------------
        // ❌ Block mixed order
        // ------------------------------------------------
        if (hasQurbaniProduct && hasOtherCategoryProduct) {
            this.popup.add(ErrorPopup, {
                title: _t("Invalid Order"),
                body: _t(
                    "If a Qurbani product exists in the order, then products from other categories are not allowed."
                ),
            });

            return;
        }

        // ------------------------------------------------
        // ✅ Create Qurbani Record
        // ------------------------------------------------
        if (hasQurbaniProduct) {
            const donor_id = currentOrder.partner.id;

            const orderLines = currentOrder.get_orderlines();

            const payload = {
                donor_id: donor_id,
                order_lines: this.prepareOrderLines(orderLines),
            };

            await this.orm.call(
                'qurbani.order',
                "create_qurbani_record",
                [payload]
            ).then((data) => {

                if (data.status === 'error') {

                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: data.body,
                    });

                    return;
                }

                if (data.status === 'success') {

                    currentOrder.set_source_document(data.name);
                    currentOrder.set_qurbani(true);

                    this.notification.add(
                        _t("Operation Successful"),
                        {
                            type: "info",
                        }
                    );
                }
            });
        }

        // Continue with normal POS flow
        return super.validateOrder(isForceValidate);
    },

    prepareOrderLines(orderLines) {
        return orderLines.map(line => ({
            product_id: line.product.id,
            quantity: line.quantity,
            price: line.price,
            qurbani_schedule: line.qurbani_schedule || null,
            remarks: line.customerNote,
        }));
    }
});