/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useService } from "@web/core/utils/hooks";
import { useState, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";

export class CustomClosingPopup extends AbstractAwaitablePopup {
    static template = "CustomClosingPopup";

    setup() {
        super.setup();

        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");

        this.state = useState({
            payments: {},
            notes: "",
        });

        onMounted(async () => {
            await this.orm.call(
                "pos.session.slip",
                "delete_session_slips_for_session",
                [this.pos.pos_session.id]
            );
        });
    }

    // -------------------------
    // UTIL
    // -------------------------

    round(val) {
        return Number(Number(val || 0).toFixed(2));
    }

    getPayment(paymentId) {
        if (paymentId === this.props.default_cash_details?.id) {
            return this.props.default_cash_details;
        }
        return (this.props.other_payment_methods || []).find(p => p.id === paymentId);
    }

    getDifference(paymentId) {
        const pm = this.getPayment(paymentId);
        if (!pm) return 0;

        const counted = this.round(this.state.payments[paymentId]?.counted);

        // IMPORTANT: backend must send expected
        const expected = this.round(pm.expected || 0);

        return counted - expected;
    }

    // -------------------------
    // VALIDATION
    // -------------------------

    canConfirm() {
        return Object.values(this.state.payments).every(p =>
            this.env.utils.isValidFloat(p.counted)
        );
    }

    async confirm() {
        const hasDiff = Object.keys(this.state.payments).some(id =>
            !this.env.utils.floatIsZero(this.getDifference(Number(id)))
        );

        if (!this.pos.config.cash_control || !hasDiff) {
            return this.closeSession();
        }

        const { confirmed } = await this.popup.add(ConfirmPopup, {
            title: _t("Confirm Closing"),
            body: _t("Differences detected. Do you want to continue?"),
        });

        if (confirmed) {
            return this.closeSession();
        }
    }

    // -------------------------
    // SESSION CLOSE
    // -------------------------

    async closeSession() {
        const cashId = this.props.default_cash_details?.id;

        const counted = this.round(this.state.payments[cashId]?.counted);

        await this.orm.call("pos.session", "post_closing_cash_details", [
            this.pos.pos_session.id,
            counted,
        ]);

        const result = await this.orm.call(
            "pos.session",
            "close_session_from_ui",
            [this.pos.pos_session.id]
        );

        if (!result.successful) {
            await this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: result.message || _t("Session closing failed"),
            });
            return;
        }

        this.pos.redirectToBackend();
    }

    // -------------------------
    // SLIPS ONLY (NO ACCOUNTING LOGIC HERE)
    // -------------------------

    async handleAddLine(paymentId, type) {
        const { amount, ref } = this.state.newLines?.[paymentId]?.[type] || {};

        if (!amount || !ref) {
            return this.popup.add(ErrorPopup, {
                title: _t("Invalid"),
                body: _t("Amount and reference required"),
            });
        }

        const slip = await this.orm.call(
            "pos.session.slip",
            "create_session_slip",
            [
                this.pos.pos_session.id,
                {
                    payment_method_id: paymentId,
                    amount: this.round(amount),
                    ref,
                    type,
                },
            ]
        );

        if (slip.status === "error") {
            return this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("Slip creation failed"),
            });
        }

        this.state.newLines[paymentId][type] = { amount: 0, ref: "" };
    }
}