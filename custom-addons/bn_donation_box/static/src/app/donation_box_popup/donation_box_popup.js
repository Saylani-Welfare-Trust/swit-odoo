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

        // 🔹 First call your custom method
        const data = await this.orm.call('key.issuance', "set_donation_amount", [payload]);

        if (data.status === 'error') {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: data.body,
            });
            return;
        }

        if (data.status === 'success') {
            this.notification.add(_t("Amount Recorded Successfully"), { type: "info" });

            // 🔹 Search for "Donation Box Receipt" product
            const product_data = await this.orm.call('product.product', 'search_read', [
                [['name', '=', 'Donation Box Receipt']],
                ['id', 'name', 'lst_price']
            ]);

            if (!product_data.length) {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: _t("Product 'Donation Box Receipt' not found. Please create it in Products."),
                });
                return;
            }

            // 🔹 Check if product is loaded in POS session
            const product = this.pos.db.get_product_by_id(product_data[0].id);
            if (!product) {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: _t("Donation Box Receipt product not loaded in POS session."),
                });
                return;
            }

            // 🔹 Add product line to current order
            const current_order = this.pos.get_order();
            if (current_order) {
                current_order.add_product(product, {
                    price: collection.amount,
                    quantity: 1
                });
            }

            // 🔹 Close popup
            this.cancel();
        }
    }
}
