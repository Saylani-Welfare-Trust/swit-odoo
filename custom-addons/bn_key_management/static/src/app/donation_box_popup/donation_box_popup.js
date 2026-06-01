/** @odoo-module **/

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from '@web/core/l10n/translation';
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

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
            collection_id: collection.id,
            lot_id: collection.lot_id,
            box_no: collection.box_no,
            amount: collection.amount,
            shop_name: collection.shop_name,
            contact_person: collection.contact_person,
            contact_number: collection.contact_number,
            box_location: collection.box_location,
            date: collection.date,
            check_validation: true
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
            // 🔹 Add product line to current order
            const current_order = this.pos.get_order();

            payload.check_validation = false

            if (!current_order.extra_data) {
                current_order.extra_data = {};
            }

            current_order.extra_data.donation_box = payload

            // 🔹 Search for "Donation Box Receipt" product
            const product_data = await this.orm.call('product.product', 'search_read', [
                [['name', '=', this.pos.company.donation_box_product]],
                ['id', 'name']
            ]);

            if (!product_data.length) {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: _t(`Product ${this.pos.company.donation_box_product} not found. Please create it in Products.`),
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

            const lineProduct = {
                ...product,
                display_name: `${product.display_name || product.name} (Box: ${collection.box_no})`,
            };

            if (current_order) {
                current_order.add_product(lineProduct, {
                    quantity: 1,
                    price_extra: collection.amount,
                    description: `Box No.: ${collection.box_no}`,
                    extras: {
                        donation_box: {
                            lot_id: collection.lot_id,
                            box_no: collection.box_no,
                            shop_name: collection.shop_name,
                            contact_person: collection.contact_person,
                            contact_number: collection.contact_number,
                            box_location: collection.box_location,
                            date: collection.date,
                        },
                    },
                });
            }

            await this.processPartner(data, current_order)

            // 🔹 Close popup
            this.cancel();
        }
    }

    /**
     * Process partner assignment
     */
    async processPartner(record, selectedOrder) {
        if (!record.donor_id) {
            return;
        }

        const partnerId = record.donor_id;
        let partner = await this.getOrLoadPartner(partnerId);
        
        if (partner) {
            this.assignPartnerToOrder(partner, selectedOrder);
        } else {
            console.warn("Partner not found in POS database:", partnerId);
        } 
    }

    /**
     * Get partner from POS DB or load from server
     */
    async getOrLoadPartner(partnerId) {
        let partner = this.pos.db.get_partner_by_id(partnerId);
        
        if (!partner) {
            partner = await this.loadPartnerFromServer(partnerId);
        }
        
        return partner;
    }

    /**
     * Load partner data from server
     */
    async loadPartnerFromServer(partnerId) {
        const partnerData = await this.orm.searchRead(
            'res.partner',
            [['id', '=', partnerId]],
            ['name', 'email', 'phone', 'street', 'city'],
            { limit: 1 }
        );
        
        if (partnerData && partnerData.length > 0) {
            this.pos.db.add_partners([partnerData[0]]);
            const partner = this.pos.db.get_partner_by_id(partnerId);
            
            return partner;
        }
        
        return null;
    }

    /**
     * Assign partner to order
     */
    assignPartnerToOrder(partner, selectedOrder) {
        selectedOrder.set_partner(partner);
        
        this.notification.add(
            `Customer set to: ${partner.name}`,
            { type: 'info' }
        );
    }
}
