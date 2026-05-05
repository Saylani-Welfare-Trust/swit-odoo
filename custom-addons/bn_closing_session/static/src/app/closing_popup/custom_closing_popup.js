/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { SaleDetailsButton } from "@point_of_sale/app/navbar/sale_details_button/sale_details_button";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

import { useService } from "@web/core/utils/hooks";
import { useState, onMounted } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useAsyncLockedMethod } from "@point_of_sale/app/utils/hooks";

import { ConnectionLostError } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";

export class CustomClosingPopup extends AbstractAwaitablePopup {
    static template = "CustomClosingPopup";
    static components = { SaleDetailsButton };

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

        this._initializePayments();

        onMounted(() => this._cleanupOldSlips());

        this.confirm = useAsyncLockedMethod(this.confirm);
    }

    /* ================= INIT ================= */

    getInitialState() {
        const payments = {};

        const add = (pm) => {
            if (pm?.id != null) payments[pm.id] = { counted: "0" };
        };

        if (this.pos.config.cash_control) {
            add(this.props.default_cash_details);
        }

        (this.props.other_payment_methods || []).forEach(add);

        return { notes: "", payments };
    }

    _initializePayments() {
        const init = (pm) => {
            if (!pm?.id) return;

            this.state.lines[pm.id] = {
                restricted: [],
                unrestricted: [],
                neutral: [],
            };

            this.state.newLines[pm.id] = {
                restricted: { bank: "", amount: 0, ref: "", record_id: 0 },
                unrestricted: { bank: "", amount: 0, ref: "", record_id: 0 },
                neutral: { bank: "", amount: 0, ref: "", record_id: 0 },
            };
        };

        init(this.props.default_cash_details);
        (this.props.other_payment_methods || []).forEach(init);
    }

    async _cleanupOldSlips() {
        try {
            await this.orm.call("pos.session.slip", "delete_session_slips_for_session", [
                this.pos.pos_session.id,
            ]);
        } catch {}
    }

    /* ================= HELPERS ================= */

    _getPayment(paymentId) {
        if (paymentId === this.props.default_cash_details?.id) {
            return this.props.default_cash_details;
        }
        return (this.props.other_payment_methods || []).find(p => p.id === paymentId);
    }

    _parseFloat(value) {
        const num = parseFloat(value);
        return Number.isFinite(num) ? num : 0;
    }

    _isValidFloat(value) {
        return this.env.utils.isValidFloat(value);
    }

    shouldShowSlipInput(pm) {
        return pm && !(pm.skip_amount_input === true || pm.skip_amount_input === "true");
    }

    shouldShowDifference(pm) {
        return this.shouldShowSlipInput(pm);
    }

    shouldShowSlipHeaders() {
        if (this.shouldShowSlipInput(this.props.default_cash_details)) return true;
        return (this.props.other_payment_methods || []).some(pm => this.shouldShowSlipInput(pm));
    }

    /* ================= DIFFERENCE ================= */

    getLinesTotal(paymentId) {
        const lines = this.state.lines[paymentId] || {};
        return ["restricted", "unrestricted", "neutral"]
            .flatMap(t => lines[t] || [])
            .reduce((sum, l) => sum + (l.amount || 0), 0);
    }

    getDifference(paymentId) {
        const pm = this._getPayment(paymentId);
        const countedRaw = this.state.payments[paymentId]?.counted;

        if (!pm || !this._isValidFloat(countedRaw)) return NaN;
        if (!this.shouldShowDifference(pm)) return 0;

        const counted = this._parseFloat(countedRaw);
        return counted + this.getLinesTotal(paymentId) - (pm.amount || 0);
    }

    getRestrictedDifference(paymentId) {
        const pm = this._getPayment(paymentId);
        const expected = pm?.breakdown?.restricted || 0;
        const actual = (this.state.lines[paymentId]?.restricted || []).reduce((s, l) => s + (l.amount || 0), 0);
        return actual - expected;
    }

    getUnrestrictedDifference(paymentId) {
        const pm = this._getPayment(paymentId);
        const expected = pm?.breakdown?.unrestricted || 0;
        const actual = (this.state.lines[paymentId]?.unrestricted || []).reduce((s, l) => s + (l.amount || 0), 0);
        return actual - expected;
    }

    getNeutralDifference(paymentId) {
        const pm = this._getPayment(paymentId);
        const expected = pm?.breakdown?.neutral || 0;
        const actual = (this.state.lines[paymentId]?.neutral || []).reduce((s, l) => s + (l.amount || 0), 0);
        return actual - expected;
    }

    formatCurrencyNeutral(value) {
        return this.env.utils.formatCurrency(this._parseFloat(value));
    }

    /* ================= VALIDATION ================= */

    getMaxDifference() {
        return Math.max(
            0,
            ...Object.keys(this.state.payments).map(id =>
                Math.abs(this.getDifference(parseInt(id))) || 0
            )
        );
    }

    hasUserAuthority() {
        return this.props.is_manager ||
            this.props.amount_authorized_diff == null ||
            this.getMaxDifference() <= this.props.amount_authorized_diff;
    }

    canConfirm() {
        for (const id of Object.keys(this.state.payments)) {
            const pm = this._getPayment(parseInt(id));
            if (!pm) continue;

            if (this.shouldShowDifference(pm) &&
                !this.env.utils.floatIsZero(this.getDifference(pm.id))) {
                return false;
            }

            if (!this._isValidFloat(this.state.payments[id]?.counted)) {
                return false;
            }
        }
        return true;
    }

    /* ================= ACTIONS ================= */

    async confirm() {
        const hasDiff = Object.keys(this.state.payments).some(id => {
            const pm = this._getPayment(parseInt(id));
            return pm && this.shouldShowDifference(pm) &&
                !this.env.utils.floatIsZero(this.getDifference(pm.id));
        });

        if (!this.pos.config.cash_control || !hasDiff) {
            return this.closeSession();
        }

        if (this.hasUserAuthority()) {
            const { confirmed } = await this.popup.add(ConfirmPopup, {
                title: _t("Payments Difference"),
                body: _t("Do you want to accept the difference?"),
            });
            if (confirmed) return this.closeSession();
            return;
        }

        await this.popup.add(ConfirmPopup, {
            title: _t("Payments Difference"),
            body: _t("Manager approval required."),
        });
    }

    async closeSession() {
        this.customerDisplay?.update({ closeUI: true });

        const synced = await this.pos.push_orders_with_closing_popup();
        if (!synced) return;

        /* CASH CONTROL */
        if (this.pos.config.cash_control) {
            const counted = this._parseFloat(
                this.state.payments[this.props.default_cash_details.id].counted
            );

            const total = counted + this.getLinesTotal(this.props.default_cash_details.id);

            const res = await this.orm.call(
                "pos.session",
                "post_closing_cash_details",
                [this.pos.pos_session.id, total]
            );

            if (!res.successful) return this.handleClosingError(res);
        }

        try {
            await this.orm.call("pos.session", "update_closing_control_state_session", [
                this.pos.pos_session.id,
                this.state.notes,
            ]);

            const bankDiffPairs = (this.props.other_payment_methods || [])
                .filter(pm => pm.type === "bank")
                .map(pm => [pm.id, this.getDifference(pm.id)]);

            const res = await this.orm.call("pos.session", "close_session_from_ui", [
                this.pos.pos_session.id,
                bankDiffPairs,
                this.state.lines,
            ]);

            if (!res.successful) return this.handleClosingError(res);

            this.pos.redirectToBackend();

        } catch (error) {
            if (error instanceof ConnectionLostError) throw error;

            await this.popup.add(ErrorPopup, {
                title: _t("Closing error"),
                body: _t("Session closing failed."),
            });

            this.pos.redirectToBackend();
        }
    }

    async handleClosingError(response) {
        await this.popup.add(ErrorPopup, {
            title: response.title || "Error",
            body: response.message,
        });
        if (response.redirect) this.pos.redirectToBackend();
    }

    /* ================= LINES ================= */

    async handleAddLine(paymentId, type = "restricted") {
        const data = this.state.newLines[paymentId]?.[type];
        if (!data) return;

        const amount = this._parseFloat(data.amount);
        const ref = data.ref;
        const bank = data.bank;

        const pm = this._getPayment(paymentId);

        if (!pm?.skip_amount_input) {
            if (!ref || amount <= 0) {
                return this.popup.add(ErrorPopup, {
                    title: _t("Invalid input"),
                    body: _t("Enter valid amount and reference."),
                });
            }

            const duplicate = Object.values(this.state.lines[paymentId] || {})
                .flat()
                .some(l => l.ref === ref);

            if (duplicate) {
                return this.popup.add(ErrorPopup, {
                    title: _t("Duplicate Ref"),
                    body: _t("Reference must be unique."),
                });
            }
        }

        const allowed = pm?.breakdown?.[type] ?? Infinity;
        const current = (this.state.lines[paymentId]?.[type] || [])
            .reduce((s, l) => s + (l.amount || 0), 0);

        if (amount > 0 && current + amount > allowed) {
            return this.popup.add(ErrorPopup, {
                title: _t("Limit exceeded"),
                body: _t("Amount exceeds allowed limit."),
            });
        }

        try {
            const slip = await this.orm.call("pos.session.slip", "create_session_slip", [
                this.pos.pos_session.id,
                { bank_id: bank, payment_method_id: paymentId, type, amount, ref }
            ]);

            if (slip.status === "error") throw new Error();

            this.state.lines[paymentId][type].push({
                id: Date.now(),
                bank,
                amount,
                ref,
                record_id: slip.id,
            });

            this.state.newLines[paymentId][type] = {
                bank: "",
                amount: 0,
                ref: "",
            };

            this.setManualCashInput(amount);

        } catch {
            await this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("Failed to create slip."),
            });
        }
    }

    async handleRemoveLine(paymentId, lineId, record_id, type = "restricted") {
        try {
            const res = await this.orm.call(
                "pos.session.slip",
                "delete_session_slip",
                [record_id]
            );

            if (res.status === "error") throw new Error();

            this.state.lines[paymentId][type] =
                this.state.lines[paymentId][type].filter(l => l.id !== lineId);

        } catch {
            await this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("Failed to delete slip."),
            });
        }
    }

    setManualCashInput(amount) {
        if (this._isValidFloat(amount)) {
            this.state.notes = "";
        }
    }

    async openDetailsPopup() {
        const action = _t("Cash control - closing");

        this.hardwareProxy.openCashbox(action);

        const { confirmed, payload } = await this.popup.add(MoneyDetailsPopup, {
            moneyDetails: this.moneyDetails,
            action,
        });

        if (!confirmed) return;

        const total = this._parseFloat(payload.total);

        this.state.payments[this.props.default_cash_details.id].counted = String(total);

        if (payload.moneyDetailsNotes) {
            this.state.notes = payload.moneyDetailsNotes;
        }

        this.moneyDetails = payload.moneyDetails;
    }

    async downloadSalesReport() {
        return this.report.doAction("point_of_sale.sale_details_report", [
            this.pos.pos_session.id,
        ]);
    }

    async cancel() {
        super.cancel();
    }

    canCancel() {
        return true;
    }
}