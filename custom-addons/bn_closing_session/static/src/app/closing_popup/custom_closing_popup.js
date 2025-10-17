/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { SaleDetailsButton } from "@point_of_sale/app/navbar/sale_details_button/sale_details_button";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConnectionLostError } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Input } from "@point_of_sale/app/generic_components/inputs/input/input";
import { useAsyncLockedMethod } from "@point_of_sale/app/utils/hooks";

export class CustomClosingPopup extends AbstractAwaitablePopup {
    static components = { SaleDetailsButton, Input };
    static template = "CustomClosingPopup";
    static props = [
        "orders_details",
        "opening_notes",
        "default_cash_details",
        "other_payment_methods",
        "is_manager",
        "amount_authorized_diff",
        "id",
        "resolve",
        "zIndex",
        "close",
        "confirmKey",
        "cancelKey",
    ];

    setup() {
        super.setup();
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.report = useService("report");
        this.hardwareProxy = useService("hardware_proxy");
        this.customerDisplay = useService("customer_display");

        this.state = useState({
            ...this.getInitialState(),
            lines: {}, // Direct line storage without add/remove logic
        });

        // Initialize line storage for each payment method
        const initializePayment = (pm) => {
            if (!pm?.id) return;
            this.state.lines[pm.id] = {
                restricted: { amount: 0, ref: "" },
                unrestricted: { amount: 0, ref: "" },
            };
        };

        if (this.props.default_cash_details) initializePayment(this.props.default_cash_details);
        (this.props.other_payment_methods || []).forEach((pm) => initializePayment(pm));

        this.confirm = useAsyncLockedMethod(this.confirm);
    }

    getInitialState() {
        const initialState = { notes: "", payments: {} };

        if (this.pos.config.cash_control && this.props.default_cash_details) {
            initialState.payments[this.props.default_cash_details.id] = { counted: "0" };
        }

        (this.props.other_payment_methods || []).forEach((pm) => {
            if (pm?.id != null) initialState.payments[pm.id] = { counted: "0" };
        });

        return initialState;
    }

    canConfirm() {
        return Object.values(this.state.payments)
            .map(v => v.counted)
            .every(this.env.utils.isValidFloat);
    }

    async confirm() {
        if (!this.pos.config.cash_control || this.env.utils.floatIsZero(this.getMaxDifference())) {
            await this.closeSession();
            return;
        }
        if (this.hasUserAuthority()) {
            const { confirmed } = await this.popup.add(ConfirmPopup, {
                title: _t("Payments Difference"),
                body: _t("Do you want to accept payments difference and post a profit/loss journal entry?"),
            });
            if (confirmed) {
                await this.closeSession();
            }
            return;
        }
        await this.popup.add(ConfirmPopup, {
            title: _t("Payments Difference"),
            body: _t(
                "The maximum difference allowed is %s.\nPlease contact your manager to accept the closing difference.",
                this.env.utils.formatCurrency(this.props.amount_authorized_diff)
            ),
            confirmText: _t("OK"),
        });
    }

    getEffectiveCounted(paymentId) {
        const counted = parseFloat(this.state.payments[paymentId]?.counted || 0);
        return counted + this.getLinesTotal(paymentId);
    }

    getDifference(paymentId) {
        if (!this.env.utils.isValidFloat(this.state.payments[paymentId]?.counted)) {
            return 0; // Return 0 instead of NaN for invalid counted
        }

        let expectedAmount = 0;
        if (paymentId === this.props.default_cash_details?.id) {
            expectedAmount = this.props.default_cash_details?.amount || 0;
        } else {
            const pm = (this.props.other_payment_methods || []).find((m) => m.id === paymentId);
            expectedAmount = pm?.amount || 0;
        }
        return this.getEffectiveCounted(paymentId) - expectedAmount;
    }

    getLinesTotal(paymentId) {
        const lines = this.state.lines[paymentId] || { restricted: { amount: 0 }, unrestricted: { amount: 0 } };
        return (parseFloat(lines.restricted.amount) || 0) + (parseFloat(lines.unrestricted.amount) || 0);
    }

    getMaxDifference() {
        const diffs = Object.keys(this.state.payments || {}).map((id) => Math.abs(this.getDifference(parseInt(id))));
        return diffs.length ? Math.max(...diffs) : 0;
    }

    hasUserAuthority() {
        return this.props.is_manager || this.props.amount_authorized_diff == null || this.getMaxDifference() <= this.props.amount_authorized_diff;
    }

    async closeSession() {
        this.customerDisplay?.update({ closeUI: true });
        const syncSuccess = await this.pos.push_orders_with_closing_popup();
        if (!syncSuccess) return;

        if (this.pos.config.cash_control) {
            const response = await this.orm.call("pos.session", "post_closing_cash_details", [this.pos.pos_session.id], {
                counted_cash: parseFloat(this.state.payments[this.props.default_cash_details.id].counted),
            });
            if (!response.successful) return this.handleClosingError(response);
        }

        try {
            await this.orm.call("pos.session", "update_closing_control_state_session", [
                this.pos.pos_session.id,
                this.state.notes,
            ]);
        } catch (error) {
            if (!error.data && error.data.message !== "This session is already closed.") {
                throw error;
            }
        }

        try {
            // Prepare the lines in the expected format
            const serverLines = {};
            
            // Process default cash details
            if (this.props.default_cash_details) {
                const paymentId = this.props.default_cash_details.id;
                const lines = this.state.lines[paymentId] || {};
                
                serverLines[paymentId] = {
                    restricted: lines.restricted && parseFloat(lines.restricted.amount) > 0 ? [{
                        amount: parseFloat(lines.restricted.amount),
                        ref: lines.restricted.ref
                    }] : [],
                    unrestricted: lines.unrestricted && parseFloat(lines.unrestricted.amount) > 0 ? [{
                        amount: parseFloat(lines.unrestricted.amount),
                        ref: lines.unrestricted.ref
                    }] : []
                };
            }

            // Process other payment methods
            (this.props.other_payment_methods || []).forEach(pm => {
                if (!pm?.id) return;
                
                const lines = this.state.lines[pm.id] || {};
                
                serverLines[pm.id] = {
                    restricted: lines.restricted && parseFloat(lines.restricted.amount) > 0 ? [{
                        amount: parseFloat(lines.restricted.amount),
                        ref: lines.restricted.ref
                    }] : [],
                    unrestricted: lines.unrestricted && parseFloat(lines.unrestricted.amount) > 0 ? [{
                        amount: parseFloat(lines.unrestricted.amount),
                        ref: lines.unrestricted.ref
                    }] : []
                };
            });

            const bankDiffPairs = this.props.other_payment_methods
                .filter(pm => pm.type === "bank")
                .map(pm => {
                    const diff = this.getDifference(pm.id);
                    // Ensure the difference is a number, if not use 0
                    return [pm.id, isNaN(diff) ? 0 : diff];
                });

            const response = await this.orm.call("pos.session", "close_session_from_ui", [
                this.pos.pos_session.id,
                bankDiffPairs,
                serverLines, // Send the formatted lines
            ]);
            
            if (!response.successful) return this.handleClosingError(response);
            this.pos.redirectToBackend();
        } catch (error) {
            if (error instanceof ConnectionLostError) throw error;
            else {
                await this.popup.add(ErrorPopup, {
                    title: _t("Closing session error"),
                    body: _t("An error has occurred when trying to close the session.\nYou will be redirected to the back-end to manually close the session."),
                });
                this.pos.redirectToBackend();
            }
        }
    }

    async handleClosingError(response) {
        await this.popup.add(ErrorPopup, {
            title: response.title || "Error",
            body: response.message,
            sound: response.type !== "alert",
        });
        if (response.redirect) this.pos.redirectToBackend();
    }

    setManualCashInput(amount) {
        if (this.env.utils.isValidFloat(amount)) this.state.notes = "";
    }

    async openDetailsPopup() {
        const action = _t("Cash control - closing");
        this.hardwareProxy.openCashbox(action);
        const { confirmed, payload } = await this.popup.add(MoneyDetailsPopup, {
            moneyDetails: this.moneyDetails,
            action,
        });
        if (confirmed) {
            const { total, moneyDetailsNotes, moneyDetails } = payload;
            this.state.payments[this.props.default_cash_details.id].counted = this.env.utils.formatCurrency(total, false);
            if (moneyDetailsNotes) this.state.notes = moneyDetailsNotes;
            this.moneyDetails = moneyDetails;
        }
    }

    async downloadSalesReport() {
        return this.report.doAction("point_of_sale.sale_details_report", [this.pos.pos_session.id]);
    }

    async cancel() {
        if (this.canCancel()) super.cancel();
    }

    canCancel() {
        return true;
    }
}