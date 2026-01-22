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
import { onMounted } from "@odoo/owl";

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
            this.state.lines[pm.id] = { restricted: [], unrestricted: [], neutral: [] };
            this.state.newLines[pm.id] = {
                restricted: { amount: 0, ref: "", record_id: 0 },
                unrestricted: { amount: 0, ref: "", record_id: 0 },
                neutral: { amount: 0, ref: "", record_id: 0 },
            };
        };

        // Helper to check if slip input should be shown for a payment method
        this.shouldShowSlipInput = (pm) => {
            if (!pm) return false;
            return !(pm.skip_slip_input === true || pm.skip_slip_input === 'true');
        };

        // Helper to check if difference should be shown for a payment method
        this.shouldShowDifference = (pm) => {
            if (!pm) return true;
            // For skip_slip_input, do not show difference (always zero)
            if (pm.skip_slip_input === true || pm.skip_slip_input === 'true') {
                return false;
            }
            return true;
        };

        // 🔥 Cleanup after UI mounts
        onMounted(async () => {
            try {
                // Delete all slips from backend
                await this.orm.call("pos.session.slip", "delete_session_slips_for_session", [
                    this.pos.pos_session.id,
                ]);
            } catch (error) {
                console.error("Slip cleanup failed:", error);
            }
        });

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
        // Only require confirmation if any non-skip payment method has a nonzero difference
        const cash = this.props.default_cash_details;
        const cashDiff = cash && this.shouldShowDifference(cash) ? this.getDifference(cash.id) : 0;
        if (cash && this.shouldShowDifference(cash) && !this.env.utils.floatIsZero(cashDiff)) {
            return false;
        }
        for (const pm of this.props.other_payment_methods || []) {
            if (this.shouldShowDifference(pm) && !this.env.utils.floatIsZero(this.getDifference(pm.id))) {
                return false;
            }
        }
        return Object.values(this.state.payments)
            .map(v => v.counted)
            .every(this.env.utils.isValidFloat);
    }

    async confirm() {
        // Only show difference confirmation if any non-skip payment method has a nonzero difference
        const cash = this.props.default_cash_details;
        const cashDiff = cash && this.shouldShowDifference(cash) ? this.getDifference(cash.id) : 0;
        let hasDiff = false;
        if (cash && this.shouldShowDifference(cash) && !this.env.utils.floatIsZero(cashDiff)) {
            hasDiff = true;
        }
        for (const pm of this.props.other_payment_methods || []) {
            if (this.shouldShowDifference(pm) && !this.env.utils.floatIsZero(this.getDifference(pm.id))) {
                hasDiff = true;
                break;
            }
        }
        if (!this.pos.config.cash_control || !hasDiff) {
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
        let pm = null;
        if (paymentId === this.props.default_cash_details?.id) {
            expectedAmount = this.props.default_cash_details?.amount || 0;
            pm = this.props.default_cash_details;
        } else {
            pm = (this.props.other_payment_methods || []).find((m) => m.id === paymentId);
            expectedAmount = pm?.amount || 0;
        }
        // For skip_slip_input, always return 0
        if (pm && (pm.skip_slip_input === true || pm.skip_slip_input === 'true')) {
            return 0;
        }
        return this.getEffectiveCounted(paymentId) - expectedAmount;
    }

    _getPaymentMethod(paymentId) {
        return paymentId === this.props.default_cash_details?.id
            ? this.props.default_cash_details
            : (this.props.other_payment_methods || []).find(m => m.id === paymentId);
    }

    getRestrictedDifference(paymentId) {
        const pm = this._getPaymentMethod(paymentId);
        const expected = pm?.breakdown?.restricted || 0;
        const actual = (this.state.lines[paymentId]?.restricted || [])
            .reduce((sum, line) => sum + (line.amount || 0), 0);
        return actual - expected;
    }

    getUnrestrictedDifference(paymentId) {
        const pm = this._getPaymentMethod(paymentId);
        const expected = pm?.breakdown?.unrestricted || 0;
        const actual = (this.state.lines[paymentId]?.unrestricted || [])
            .reduce((sum, line) => sum + (line.amount || 0), 0);
        return actual - expected;
    }

    getLinesTotal(paymentId) {
        const lines = this.state.lines[paymentId] || { restricted: [], unrestricted: [] };
        const restrictedTotal = (lines.restricted || []).reduce((sum, line) => sum + (line.amount || 0), 0);
        const unrestrictedTotal = (lines.unrestricted || []).reduce((sum, line) => sum + (line.amount || 0), 0);
        const neutralTotal = (lines.neutral || []).reduce((sum, l) => sum + (l.amount || 0), 0);

        return restrictedTotal + unrestrictedTotal + neutralTotal;
    }

    getNeutralDifference(paymentId) {
    const pm = this._getPaymentMethod(paymentId);
    const expected = pm?.breakdown?.neutral || 0;
    const actual = (this.state.lines[paymentId]?.neutral || [])
        .reduce((sum, line) => sum + (line.amount || 0), 0);
    return actual - expected;
}

    // Safely format amounts for neutral rows to avoid undefined/NaN reaching formatCurrency
    formatCurrencyNeutral(value) {
        const num = Number(value);
        return this.env.utils.formatCurrency(Number.isFinite(num) ? num : 0);
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

        console.log(this.state.lines);

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
    async handleAddLine(paymentId, type = "restricted") {
        const { amount, ref } = this.state.newLines[paymentId][type];
        const amountNum = parseFloat(amount);

        // Basic validation
        if (!amount || !ref || isNaN(amountNum)) {
            this.popup.add(ErrorPopup, {
                title: _t("Invalid input"),
                body: _t("Please enter a valid Amount and Ref."),
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
        
        const payload = {
            payment_method_id: paymentId,
            type: type,
            amount: amountNum,
            ref: ref
        }
        
        const slip = await this.orm.call("pos.session.slip", "create_session_slip", [
            this.pos.pos_session.id,
            payload,
        ]);

        if (slip.status == 'error') {
            await this.popup.add(ErrorPopup, {
                title: _t("Session Slip Error"),
                body: _t("Unable to add slip to session please check your internet connection."),
            });
        }
        
        if (slip.status == 'success') {
            this.state.lines[paymentId][type].push({ id, amount: amountNum, ref, record_id: slip.id });
        }
        
        // Reset input
        this.state.newLines[paymentId][type] = { amount: 0, ref: "" };
        
        this.setManualCashInput(amountNum);
    }
    
    async handleRemoveLine(paymentId, lineId, record_id, type = "restricted") {
        const slip = await this.orm.call("pos.session.slip", "delete_session_slip", [record_id]);
        
        if (slip.status == 'error') {
            await this.popup.add(ErrorPopup, {
                title: _t("Session Slip Error"),
                body: _t("Unable to add slip to session please check your internet connection."),
            });
        }

        if (slip.status == 'success') {
            this.state.lines[paymentId][type] = this.state.lines[paymentId][type].filter(line => line.id !== lineId);
        }
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
