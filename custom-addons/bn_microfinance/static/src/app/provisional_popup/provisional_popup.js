/** @odoo-module */

import { ProvisionalPopup } from "@bn_pos_custom_action/app/provisional_popup/provisional_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";


// Microfinance security deposit (action_type 'mf').
patch(ProvisionalPopup.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.microfinance_request_no = '';
    },

    get hasProgramBody() {
        return this.action_type === 'mf' || super.hasProgramBody;
    },

    updateMicrofinanceRequestNo(event) {
        this.state.microfinance_request_no = event.target.value;
    },

    async confirmProgram(selectedOrder) {
        if (this.action_type !== 'mf') {
            return super.confirmProgram(...arguments);
        }
        await this.confirmMicrofinanceSecurityDeposit(selectedOrder);
        return true;
    },

    async confirmMicrofinanceSecurityDeposit(selectedOrder) {
        if (!this.state.microfinance_request_no) {
            this.notification.add(
                "Please enter a Microfinance Request No.",
                { type: 'warning' }
            );
            return;
        }

        const payload = {
            microfinance_request_no: this.state.microfinance_request_no,
            amount: this.state.amount,
            security_desposit: true
        }

        const data = await this.orm.call('microfinance.installment', "get_microfinance_security_deposit", [payload]);

        if (data.status !== 'success') {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: data.body || _t("Microfinance request not found."),
            });
            return;
        }

        payload.security_deposit_id = data.deposit_id || null;  // Will be null if deposit doesn't exist
        payload.microfinance_id = data.id;  // Store microfinance_id for creating record if needed
        payload.amount = data.amount;  // Store amount from microfinance request

        if (data.state === 'paid') {
            this.notification.add(_t("Security deposit already paid"), {
                type: "info",
            });
            this.cancel();
            return;
        }

        const productName = this.pos.company.microfinance_security_depsoit_product;
        const securityProduct = await this.orm.searchRead(
            'product.product',
            [
                ['name', '=', productName],
                ['detailed_type', '=', 'service'],
                ['available_in_pos', '=', true]
            ],
            ['id'],
            { limit: 1 }
        );
        const product = securityProduct.length && this.pos.db.get_product_by_id(securityProduct[0].id);
        if (!product) {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t(`${productName} product not loaded in POS session.`),
            });
            return;
        }

        if (data.deposit_exists) {
            this.notification.add(_t("Existing deposit found"), {
                type: "info",
            });
        } else {
            this.notification.add(_t("Security deposit will be created upon payment"), {
                type: "info",
            });
        }

        // Set customer from donee_id
        if (data.donee_id) {
            const partner = await this.getOrLoadPartner(data.donee_id);
            if (partner) {
                this.assignPartnerToOrder(partner, selectedOrder);
            }
        }

        if (!selectedOrder.extra_data) {
            selectedOrder.extra_data = {};
        }
        selectedOrder.extra_data.microfinance = payload;

        selectedOrder.add_product(product, {
            quantity: 1,
            price_extra: data.amount,
        });
        selectedOrder.set_receive_voucher(true);

        this.cancel();
    },
});
