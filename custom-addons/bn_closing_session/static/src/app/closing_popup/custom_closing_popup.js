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
        "bank_list",
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
            lines: {},
            newLines: {},
        });

        const initializePayment = (pm) => {
            if (!pm?.id) return;
            this.state.lines[pm.id] = { restricted: [], unrestricted: [], neutral: [] };
            this.state.newLines[pm.id] = {
                restricted: { bank: "", amount: 0, ref: "", record_id: 0 },
                unrestricted: { bank: "", amount: 0, ref: "", record_id: 0 },
                neutral: { bank: "", amount: 0, ref: "", record_id: 0 },
            };
        };

        this.shouldShowSlipInput = (pm) => pm && !(pm.skip_amount_input === true || pm.skip_amount_input === 'true');

        this.shouldShowSlipHeaders = () => {
            if (this.shouldShowSlipInput(this.props.default_cash_details)) return true;
            return (this.props.other_payment_methods || []).some(pm => this.shouldShowSlipInput(pm));
        };

        this.shouldShowDifference = (pm) => pm && !(pm.skip_amount_input === true || pm.skip_amount_input === 'true');

        onMounted(async () => {
            try {
                await this.orm.call("pos.session.slip", "delete_session_slips_for_session", [
                    this.pos.pos_session.id,
                ]);
            } catch (error) {
                console.error("Slip cleanup failed:", error);
            }
        });

        if (this.props.default_cash_details) initializePayment(this.props.default_cash_details);
        (this.props.other_payment_methods || []).forEach(initializePayment);

        this.handleAddLine = this.handleAddLine.bind(this);
        this.handleRemoveLine = this.handleRemoveLine.bind(this);

        this.confirm = useAsyncLockedMethod(this.confirm);
    }

    getInitialState() {
        const initialState = { notes: "", payments: {} };
        if (this.pos.config.cash_control && this.props.default_cash_details) {
            initialState.payments[this.props.default_cash_details.id] = { counted: "0" };
        }
        (this.props.other_payment_methods || []).forEach(pm => {
            if (pm?.id != null) initialState.payments[pm.id] = { counted: "0" };
        });
        return initialState;
    }

    canConfirm() {
        const cash = this.props.default_cash_details;
        if (cash && this.shouldShowDifference(cash) && !this.env.utils.floatIsZero(this.getDifference(cash.id))) {
            return false;
        }
        for (const pm of this.props.other_payment_methods || []) {
            if (this.shouldShowDifference(pm) && !this.env.utils.floatIsZero(this.getDifference(pm.id))) {
                return false;
            }
        }
        return Object.values(this.state.payments).every(v => this.env.utils.isValidFloat(v.counted));
    }

    async confirm() {
        const cash = this.props.default_cash_details;
        let hasDiff = false;
        if (cash && this.shouldShowDifference(cash) && !this.env.utils.floatIsZero(this.getDifference(cash.id))) {
            hasDiff = true;
        }
        for (const pm of this.props.other_payment_methods || []) {
            if (this.shouldShowDifference(pm) && !this.env.utils.floatIsZero(this.getDifference(pm.id))) {
                hasDiff = true;
                break;
            }
        }

        if (!this.pos.config.cash_control || !hasDiff) return await this.closeSession();

        if (this.hasUserAuthority()) {
            const { confirmed } = await this.popup.add(ConfirmPopup, {
                title: _t("Payments Difference"),
                body: _t("Do you want to accept payments difference and post a profit/loss journal entry?"),
            });
            if (confirmed) await this.closeSession();
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
        return parseFloat(this.state.payments[paymentId]?.counted || 0) + this.getLinesTotal(paymentId);
    }

    getDifference(paymentId) {
        const payment = paymentId === this.props.default_cash_details?.id
            ? this.props.default_cash_details
            : (this.props.other_payment_methods || []).find(m => m.id === paymentId);

        if (!payment || !this.env.utils.isValidFloat(this.state.payments[paymentId]?.counted)) return NaN;

        if (payment.skip_amount_input === true || payment.skip_amount_input === 'tru') return 0;

        const expected = payment.amount || 0;
        return this.getEffectiveCounted(paymentId) - expected;
    }

    _getPaymentMethod(paymentId) {
        return paymentId === this.props.default_cash_details?.id
            ? this.props.default_cash_details
            : (this.props.other_payment_methods || []).find(m => m.id === paymentId);
    }

    getRestrictedDifference(paymentId) {
        const pm = this._getPaymentMethod(paymentId);
        const expected = pm?.breakdown?.restricted || 0;
        const actual = (this.state.lines[paymentId]?.restricted || []).reduce((sum, l) => sum + (l.amount || 0), 0);
        return actual - expected;
    }

    getUnrestrictedDifference(paymentId) {
        const pm = this._getPaymentMethod(paymentId);
        const expected = pm?.breakdown?.unrestricted || 0;
        const actual = (this.state.lines[paymentId]?.unrestricted || []).reduce((sum, l) => sum + (l.amount || 0), 0);
        return actual - expected;
    }

    getNeutralDifference(paymentId) {
        const pm = this._getPaymentMethod(paymentId);
        const expected = pm?.breakdown?.neutral || 0;
        const actual = (this.state.lines[paymentId]?.neutral || []).reduce((sum, l) => sum + (l.amount || 0), 0);
        return actual - expected;
    }

    getLinesTotal(paymentId) {
        const lines = this.state.lines[paymentId] || { restricted: [], unrestricted: [], neutral: [] };
        return ["restricted", "unrestricted", "neutral"].reduce(
            (sum, type) => sum + (lines[type] || []).reduce((s, l) => s + (l.amount || 0), 0),
            0
        );
    }

    formatCurrencyNeutral(value) {
        const num = Number(value);
        return this.env.utils.formatCurrency(Number.isFinite(num) ? num : 0);
    }

    getMaxDifference() {
        const diffs = Object.keys(this.state.payments || {}).map(id => Math.abs(this.getDifference(parseInt(id))));
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
            const counted = parseFloat(this.state.payments[this.props.default_cash_details.id].counted);
            const response = await this.orm.call("pos.session", "post_closing_cash_details", [
                this.pos.pos_session.id,
                counted
            ]);
            if (!response.successful) return this.handleClosingError(response);
        }

        try {
            await this.orm.call("pos.session", "update_closing_control_state_session", [
                this.pos.pos_session.id,
                this.state.notes,
            ]);
        } catch (error) {
            if (!error.data || error.data.message !== "This session is already closed.") throw error;
        }

        try {
            const bankDiffPairs = (this.props.other_payment_methods || [])
                .filter(pm => pm.type === "bank")
                .map(pm => [pm.id, this.getDifference(pm.id)]);

            const response = await this.orm.call("pos.session", "close_session_from_ui", [
                this.pos.pos_session.id,
                bankDiffPairs,
                this.state.lines,
            ]);
            if (!response.successful) return this.handleClosingError(response);
            this.pos.redirectToBackend();
        } catch (error) {
            if (error instanceof ConnectionLostError) throw error;
            await this.popup.add(ErrorPopup, {
                title: _t("Closing session error"),
                body: _t("An error has occurred when trying to close the session.\nYou will be redirected to the back-end to manually close the session."),
            });
            this.pos.redirectToBackend();
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

    async handleAddLine(paymentId, type = "restricted") {
        const { amount, ref, bank } = this.state.newLines[paymentId][type];
        const amountNum = parseFloat(amount);

        const pm = paymentId === this.props.default_cash_details?.id
            ? this.props.default_cash_details
            : (this.props.other_payment_methods || []).find(m => m.id === paymentId);

        // Only validate amount/ref & duplicates if skip_amount_input is true
        if (!pm?.skip_amount_input) {
            if (!amount || !ref || isNaN(amountNum)) {
                this.popup.add(ErrorPopup, {
                    title: _t("Invalid input"),
                    body: _t("Please enter a valid Amount and Ref."),
                });
                return;
            }

            const duplicate = Object.values(this.state.lines[paymentId] || {}).flat().some(line => line.ref === ref);
            if (duplicate) {
                this.popup.add(ErrorPopup, {
                    title: _t("Duplicate Ref"),
                    body: _t("Slip No (Ref) must be unique for this payment method."),
                });
                return;
            }
        }

        const currentTotal = (this.state.lines[paymentId][type] || []).reduce((sum, line) => sum + (line.amount || 0), 0);

        const allowed = pm?.breakdown?.[type] ?? Number.POSITIVE_INFINITY;
        if (currentTotal + amountNum > allowed) {
            this.popup.add(ErrorPopup, {
                title: _t("Limit exceeded"),
                body: _t(`${type.charAt(0).toUpperCase() + type.slice(1)} amount cannot exceed ` +
                    this.env.utils.formatCurrency(Number.isFinite(allowed) ? allowed : 0)),
            });
            return;
        }

        const pmBank = this.props.bank_list.find(b => b.id == bank);
        const bank_name = pmBank ? pmBank.name : '';
        const bank_id = pmBank ? pmBank.id : '';

        const id = Date.now();
        const payload = { bank_id: bank_id, payment_method_id: paymentId, type, amount: amountNum, ref };
        const slip = await this.orm.call("pos.session.slip", "create_session_slip", [this.pos.pos_session.id, payload]);

        if (slip.status === 'error') {
            await this.popup.add(ErrorPopup, { title: _t("Session Slip Error"), body: _t("Unable to add slip to session please check your internet connection.") });
        } else {
            this.state.lines[paymentId][type].push({ id, bank: bank_name, amount: amountNum, ref, record_id: slip.id });
        }

        this.state.newLines[paymentId][type] = { amount: 0, ref: "", bank: "" };
        this.setManualCashInput(amountNum);
    }

    async handleRemoveLine(paymentId, lineId, record_id, type = "restricted") {
        const slip = await this.orm.call("pos.session.slip", "delete_session_slip", [record_id]);
        if (slip.status === 'error') {
            await this.popup.add(ErrorPopup, { title: _t("Session Slip Error"), body: _t("Unable to add slip to session please check your internet connection.") });
        } else {
            this.state.lines[paymentId][type] = this.state.lines[paymentId][type].filter(line => line.id !== lineId);
        }
    }

    setManualCashInput(amount) {
        if (this.env.utils.isValidFloat(amount)) this.state.notes = "";
    }

    async openDetailsPopup() {
        const action = _t("Cash control - closing");
        this.hardwareProxy.openCashbox(action);
        const { confirmed, payload } = await this.popup.add(MoneyDetailsPopup, { moneyDetails: this.moneyDetails, action });
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
