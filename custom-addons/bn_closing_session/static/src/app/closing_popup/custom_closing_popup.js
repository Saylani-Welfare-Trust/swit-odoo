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

    // --- setup() : make forEach safe even if other_payment_methods is null/undefined
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
            lines: {},       // all lines per payment method + type
            newLines: {},    // new line inputs per payment method + type
        });

        const initializePayment = (pm) => {
            if (!pm?.id) return;
            this.state.lines[pm.id] = { restricted: [], unrestricted: [] };
            this.state.newLines[pm.id] = {
                restricted: { amount: 0, ref: "" },
                unrestricted: { amount: 0, ref: "" },
            };
        };

        if (this.props.default_cash_details) initializePayment(this.props.default_cash_details);
        (this.props.other_payment_methods || []).forEach((pm) => initializePayment(pm));

        this.handleAddLine = this.handleAddLine.bind(this);
        this.handleRemoveLine = this.handleRemoveLine.bind(this);

        this.confirm = useAsyncLockedMethod(this.confirm);
    }

    // --- getInitialState(): guard other_payment_methods
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

    // --- getDifference(): don't crash if pm not found
    getDifference(paymentId) {
        if (!this.env.utils.isValidFloat(this.state.payments[paymentId]?.counted)) {
            return NaN;
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
        const lines = this.state.lines[paymentId] || { restricted: [], unrestricted: [] };
        const restrictedTotal = (lines.restricted || []).reduce((sum, line) => sum + (line.amount || 0), 0);
        const unrestrictedTotal = (lines.unrestricted || []).reduce((sum, line) => sum + (line.amount || 0), 0);
        return restrictedTotal + unrestrictedTotal;
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
            const bankDiffPairs = this.props.other_payment_methods
                .filter(pm => pm.type === "bank")
                .map(pm => [pm.id, this.getDifference(pm.id)]);

            const response = await this.orm.call("pos.session", "close_session_from_ui", [
                this.pos.pos_session.id,
                bankDiffPairs,
                this.state.lines,   // <-- 🔥 add your restricted/unrestricted lines here
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

    // --- handleAddLine(): compute 'allowed' from cash OR matching other_payment_method
    handleAddLine(paymentId, type = "restricted") {
        const { amount, ref } = this.state.newLines[paymentId][type];
        const amountNum = parseFloat(amount);

        // Basic validation
        if (!amount || !ref || isNaN(amountNum) || amountNum <= 0) {
            this.popup.add(ErrorPopup, {
                title: _t("Invalid input"),
                body: _t("Please enter a valid Amount and Ref."),
            });
            return;
        }

        // 🚨 Allow only 1 line per payment method + type
        if ((this.state.lines[paymentId][type] || []).length >= 1) {
            this.popup.add(ErrorPopup, {
                title: _t("Limit reached"),
                body: _t(`Only one ${type} line is allowed for this payment method.`),
            });
            return;
        }

        // Duplicate slip check (within this payment method)
        const duplicate = Object.values(this.state.lines[paymentId] || {})
            .flat()
            .some((line) => line.ref === ref);
        if (duplicate) {
            this.popup.add(ErrorPopup, {
                title: _t("Duplicate Ref"),
                body: _t("Slip No (Ref) must be unique for this payment method."),
            });
            return;
        }

        // Sum current total for this type
        const currentTotal = (this.state.lines[paymentId][type] || [])
            .reduce((sum, line) => sum + (line.amount || 0), 0);

        // 👉 Determine allowed based on matching payment method's breakdown
        const isCash = paymentId === this.props.default_cash_details?.id;
        const cashBreakdown = this.props.default_cash_details?.breakdown;
        const pm = isCash ? null : (this.props.other_payment_methods || []).find((m) => m.id === paymentId);
        const pmBreakdown = isCash ? cashBreakdown : pm?.breakdown;

        // If no breakdown exists, don't enforce a cap (allowed = Infinity)
        const allowed = pmBreakdown?.[type] ?? Number.POSITIVE_INFINITY;

        if (currentTotal + amountNum > allowed) {
            this.popup.add(ErrorPopup, {
                title: _t("Limit exceeded"),
                body: _t(
                    `${type.charAt(0).toUpperCase() + type.slice(1)} amount cannot exceed ` +
                    this.env.utils.formatCurrency(Number.isFinite(allowed) ? allowed : 0)
                ),
            });
            return;
        }

        // Add line
        const id = Date.now();
        this.state.lines[paymentId][type].push({ id, amount: amountNum, ref });

        // Reset input
        this.state.newLines[paymentId][type] = { amount: 0, ref: "" };

        this.setManualCashInput(amountNum);
    }

    handleRemoveLine(paymentId, lineId, type = "restricted") {
        this.state.lines[paymentId][type] = this.state.lines[paymentId][type].filter(line => line.id !== lineId);
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
