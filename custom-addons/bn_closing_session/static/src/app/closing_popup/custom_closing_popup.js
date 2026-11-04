/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { SaleDetailsButton } from "@point_of_sale/app/navbar/sale_details_button/sale_details_button";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useService } from "@web/core/utils/hooks";
import { useState, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useAsyncLockedMethod } from "@point_of_sale/app/utils/hooks";

export class CustomClosingPopup extends AbstractAwaitablePopup {
    static components = { SaleDetailsButton };
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
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.action = useService("action");
        this.hardwareProxy = useService("hardware_proxy");

        this.state = useState({
            notes: "",
            payments: {},
            lines: {},
            newLines: {},
            ...this._getInitialState(),
        });

        this._getPaymentMethod = (id) =>
            id === this.props.default_cash_details?.id
                ? this.props.default_cash_details
                : (this.props.other_payment_methods || []).find((m) => m.id === id);

        const initPayment = (pm) => {
            if (!pm?.id) return;
            this.state.lines[pm.id] = { restricted: [], unrestricted: [], neutral: [] };
            this.state.newLines[pm.id] = {
                restricted: this._getNewLine(pm.id, "restricted"),
                unrestricted: this._getNewLine(pm.id, "unrestricted"),
                neutral: this._getNewLine(pm.id, "neutral"),
            };
            this.state.payments[pm.id] = this.state.payments[pm.id] || { counted: "0" };
        };

        if (this.props.default_cash_details) initPayment(this.props.default_cash_details);
        (this.props.other_payment_methods || []).forEach(initPayment);

        onMounted(async () => {
            try {
                await this.orm.call("pos.session.slip", "delete_session_slips_for_session", [this.pos.pos_session.id]);
            } catch (e) {
                console.warn("Slip cleanup failed", e);
            }
        });

        this.handleAddLine = this.handleAddLine.bind(this);
        this.handleRemoveLine = this.handleRemoveLine.bind(this);
        this.confirm = useAsyncLockedMethod(this.confirm.bind(this));
    }

    _getInitialState() {
        const s = { payments: {} };
        if (this.props.default_cash_details) {
            s.payments[this.props.default_cash_details.id] = { counted: "0" };
        }
        (this.props.other_payment_methods || []).forEach((pm) => {
            if (pm?.id != null) s.payments[pm.id] = { counted: "0" };
        });
        return s;
    }

    getDifference(paymentId) {
        const pm = this._getPaymentMethod(paymentId);
        const counted = parseFloat(this.state.payments[paymentId]?.counted || 0);
        const linesTotal = this._getLinesTotal(paymentId);
        const expected = pm?.amount || 0;
        return counted + linesTotal - expected;
    }

    getRestrictedDifference(paymentId) {
        const pm = this._getPaymentMethod(paymentId);
        const expected = pm?.breakdown?.restricted || 0;
        const actual = (this.state.lines[paymentId]?.restricted || []).reduce((a, l) => a + (l.amount || 0), 0);
        return actual - expected;
    }

    getUnrestrictedDifference(paymentId) {
        const pm = this._getPaymentMethod(paymentId);
        const expected = pm?.breakdown?.unrestricted || 0;
        const actual = (this.state.lines[paymentId]?.unrestricted || []).reduce((a, l) => a + (l.amount || 0), 0);
        return actual - expected;
    }

    getNeutralDifference(paymentId) {
        const pm = this._getPaymentMethod(paymentId);
        const expected = pm?.breakdown?.neutral || 0;
        const actual = (this.state.lines[paymentId]?.neutral || []).reduce((a, l) => a + (l.amount || 0), 0);
        return actual - expected;
    }

    _getLinesTotal(paymentId) {
        const lines = this.state.lines[paymentId] || {};
        const sum = (arr) => (arr || []).reduce((a, x) => a + (x.amount || 0), 0);
        return sum(lines.restricted) + sum(lines.unrestricted) + sum(lines.neutral);
    }

    shouldShowSlipInput(pm) {
        return pm && !(pm.skip_amount_input === true || pm.skip_amount_input === "true");
    }

    shouldShowSlipHeaders() {
        return (
            this.shouldShowSlipInput(this.props.default_cash_details) ||
            (this.props.other_payment_methods || []).some((pm) => this.shouldShowSlipInput(pm))
        );
    }

    formatCurrencyNeutral(value) {
        const num = Number(value);
        return this.env.utils.formatCurrency(Number.isFinite(num) ? num : 0);
    }

    /**
     * Part of the expected breakdown amount for that payment method / type
     * that is not covered by slips yet. Several slips can be added (e.g. five
     * slips of 2,000 for 10,000) as long as they add up to the expected amount.
     */
    getRemainingAmount(paymentId, type) {
        const pm = this._getPaymentMethod(paymentId);
        const expected = pm?.breakdown?.[type] || 0;
        const added = (this.state.lines[paymentId]?.[type] || []).reduce((a, l) => a + (l.amount || 0), 0);
        return expected - added;
    }

    hasRemainingAmount(paymentId, type) {
        return !this.env.utils.floatIsZero(this.getRemainingAmount(paymentId, type));
    }

    _formatAmountInput(value) {
        return value.toFixed(this.pos.currency.decimal_places);
    }

    _getNewLine(paymentId, type) {
        return {
            bank: "0",
            ref: "",
            amount: this._formatAmountInput(this.getRemainingAmount(paymentId, type)),
            record_id: 0,
        };
    }

    getBankName(bankId) {
        const bank = (this.props.bank_list || []).find((b) => String(b.id) === String(bankId));
        return bank ? bank.name : "";
    }

    _getTypeLabel(type) {
        if (type === "restricted") return this.pos.company.restricted_category;
        if (type === "unrestricted") return this.pos.company.unrestricted_category;
        return _t("Non-Donation");
    }

    async handleAddLine(paymentId, type = "restricted") {
        const pm = this._getPaymentMethod(paymentId);
        const remaining = this.getRemainingAmount(paymentId, type);

        if (this.env.utils.floatIsZero(remaining)) {
            return;
        }

        const { ref, bank, amount } = this.state.newLines[paymentId][type];
        const isBankInvalid = !bank || bank === "0";

        if (this.shouldShowSlipInput(pm) && (!ref || isBankInvalid)) {
            this.popup.add(ErrorPopup, {
                title: _t("Invalid Input"),
                body: _t("Bank and Slip No. are required."),
            });
            return;
        }

        // === NEW: Check for duplicate slip number ===
        if (ref && ref.trim()) {
            const allExistingRefs = [];
            for (const pid in this.state.lines) {
                for (const t of ['restricted', 'unrestricted', 'neutral']) {
                    if (this.state.lines[pid][t]) {
                        this.state.lines[pid][t].forEach(line => {
                            if (line.ref) {
                                allExistingRefs.push(line.ref.trim().toLowerCase());
                            }
                        });
                    }
                }
            }
            
            if (allExistingRefs.includes(ref.trim().toLowerCase())) {
                this.popup.add(ErrorPopup, {
                    title: _t("Duplicate Slip No."),
                    body: _t(`The slip number "${ref}" has already been added. Please use a unique slip number.`),
                });
                return;
            }
        }
        // ==============================================

        // Without an amount input the slip simply covers whatever is left.
        let numAmount = this.shouldShowSlipInput(pm) ? parseFloat(amount) : remaining;
        const isAmountInvalid =
            isNaN(numAmount) ||
            this.env.utils.floatIsZero(numAmount) ||
            Math.sign(numAmount) !== Math.sign(remaining) ||
            (Math.abs(numAmount) > Math.abs(remaining) && !this.env.utils.floatIsZero(remaining - numAmount));

        if (isAmountInvalid) {
            this.popup.add(ErrorPopup, {
                title: _t("Invalid Amount"),
                body: _t(
                    `Slip amount must be between 0 and the remaining amount (${this.env.utils.formatCurrency(remaining)}).`
                ),
            });
            return;
        }

        // Use the exact remaining amount for the last slip so the slips add up
        // to the expected total without rounding differences.
        if (this.env.utils.floatIsZero(remaining - numAmount)) {
            numAmount = remaining;
        }

        const slip = await this.orm.call("pos.session.slip", "create_session_slip", [
            this.pos.pos_session.id,
            {
                payment_method_id: paymentId,
                type: type,
                amount: numAmount || 0,
                ref: ref || "",
                bank_id: bank !== "0" ? parseInt(bank, 10) : false,
            },
        ]);

        if (slip?.status === "error") {
            this.popup.add(ErrorPopup, { title: _t("Error"), body: _t(slip.message || "Slip creation failed.") });
            return;
        }

        this.state.lines[paymentId][type].push({
            id: Date.now(),
            amount: numAmount || 0,
            ref: ref || "",
            bank: bank,
            record_id: slip.id,
        });

        // Keep the selected bank for the next slip and prefill the amount that is still left.
        this.state.newLines[paymentId][type] = { ...this._getNewLine(paymentId, type), bank: bank };
    }

    async handleRemoveLine(paymentId, lineId, recordId, type) {
        const res = await this.orm.call("pos.session.slip", "delete_session_slip", [recordId]);
        if (res?.status !== "error") {
            this.state.lines[paymentId][type] = this.state.lines[paymentId][type].filter((l) => l.id !== lineId);
            this.state.newLines[paymentId][type].amount = this._formatAmountInput(
                this.getRemainingAmount(paymentId, type)
            );
        }
    }

    canConfirm() {
        return Object.values(this.state.payments).every((v) => this.env.utils.isValidFloat(v.counted));
    }

    canCancel() {
        return true;
    }

    /**
     * Payment methods whose money is deposited by slip (per category).
     */
    _slipMethods() {
        const methods = [];
        if (this.pos.config.cash_control && this.props.default_cash_details?.use_slips) {
            methods.push(this.props.default_cash_details);
        }
        for (const pm of this.props.other_payment_methods || []) {
            if (pm.use_slips) {
                methods.push(pm);
            }
        }
        return methods;
    }

    async confirm() {
        // every category with an amount needs its deposit slip (with a bank)
        for (const pm of this._slipMethods()) {
            const lines = this.state.lines[pm.id] || {};
            for (const type of ["restricted", "unrestricted", "neutral"]) {
                const expected = pm.breakdown?.[type] || 0;
                if (this.env.utils.floatIsZero(expected)) {
                    continue;
                }
                const typeLines = lines[type] || [];
                if (!typeLines.length) {
                    await this.popup.add(ErrorPopup, {
                        title: _t("Deposit Slip Missing"),
                        body: _t("Please add the deposit slip of every category of \"%s\".", pm.name),
                    });
                    return;
                }
                if (typeLines.some((line) => !line.bank || line.bank === "0" || line.bank === 0)) {
                    await this.popup.add(ErrorPopup, {
                        title: _t("Validation Error"),
                        body: _t("Please select a bank for all slip lines of \"%s\".", pm.name),
                    });
                    return;
                }
                // several slips per category: together they must cover it exactly
                const remaining = this.getRemainingAmount(pm.id, type);
                if (!this.env.utils.floatIsZero(remaining)) {
                    await this.popup.add(ErrorPopup, {
                        title: _t("Validation Error"),
                        body: _t(
                            "Slips of \"%s\" (%s Amount) total %s but the expected amount is %s.",
                            pm.name,
                            this._getTypeLabel(type),
                            this.env.utils.formatCurrency(expected - remaining),
                            this.env.utils.formatCurrency(expected)
                        ),
                    });
                    return;
                }
            }
        }

        await this.closeSession();
    }

    async closeSession() {
        const ok = await this.pos.push_orders_with_closing_popup();
        if (!ok) return;

        const bankDiffPairs = (this.props.other_payment_methods || [])
            .filter((p) => p.type === "bank" && !p.use_slips)
            .map((p) => [p.id, this.getDifference(p.id)]);

        // the cash left in the drawer once the slips are deposited
        const cash = this.props.default_cash_details;
        const cashCounted = this.pos.config.cash_control && cash
            ? parseFloat(this.state.payments[cash.id]?.counted || 0) || 0
            : null;

        const response = await this.orm.call("pos.session", "close_session_from_ui", [
            this.pos.pos_session.id,
            bankDiffPairs,
            this.state.lines,
            cashCounted,
        ]);

        if (!response?.successful) {
            await this.popup.add(ErrorPopup, {
                title: response.title || _t("Error"),
                body: response.message,
            });
            if (response.redirect) this.pos.redirectToBackend();
            return;
        }

        this.pos.redirectToBackend();
    }

    async cancel() {
        if (this.canCancel()) super.cancel();
    }

    async downloadSalesReport() {
        const session = this.pos.pos_session;
        const action = {
            type: "ir.actions.report",
            report_name: "point_of_sale.report_saledetails",
            report_type: "qweb-pdf",
            data: { session_id: session.id, config_id: session.config_id.id },
            context: { active_ids: [session.id] },
        };
        this.action.doAction(action);
    }
}