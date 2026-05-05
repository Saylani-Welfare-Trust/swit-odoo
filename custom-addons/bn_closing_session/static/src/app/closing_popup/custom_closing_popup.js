/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { SaleDetailsButton } from "@point_of_sale/app/navbar/sale_details_button/sale_details_button";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { useService } from "@web/core/utils/hooks";
import { useState, onMounted } from "@odoo/owl";
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
        this.report = useService("report");
        this.hardwareProxy = useService("hardware_proxy");
        this.customerDisplay = useService("customer_display");

        // -----------------------------
        // SAFE STATE INIT
        // -----------------------------
        this.state = useState({
            notes: "",
            payments: {},
            lines: {},
            newLines: {},
            ...this.getInitialState(),
        });

        // -----------------------------
        // SAFE HELPERS (IMPORTANT FIX)
        // -----------------------------
        this.shouldShowSlipInput = (pm) =>
            pm && !(pm.skip_amount_input === true || pm.skip_amount_input === "true");

        this.shouldShowSlipHeaders = () => {
            return (
                this.shouldShowSlipInput(this.props.default_cash_details) ||
                (this.props.other_payment_methods || []).some((pm) =>
                    this.shouldShowSlipInput(pm)
                )
            );
        };

        this.shouldShowDifference = this.shouldShowSlipInput;

        this._getPaymentMethod = (id) =>
            id === this.props.default_cash_details?.id
                ? this.props.default_cash_details
                : (this.props.other_payment_methods || []).find((m) => m.id === id);

        // -----------------------------
        // INIT PAYMENT STRUCTURE
        // -----------------------------
        const initPayment = (pm) => {
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

            this.state.payments[pm.id] = this.state.payments[pm.id] || {
                counted: "0",
            };
        };

        if (this.props.default_cash_details) {
            initPayment(this.props.default_cash_details);
        }

        (this.props.other_payment_methods || []).forEach(initPayment);

        // -----------------------------
        // REMOVE OLD SESSIONS SLIPS
        // -----------------------------
        onMounted(async () => {
            try {
                await this.orm.call(
                    "pos.session.slip",
                    "delete_session_slips_for_session",
                    [this.pos.pos_session.id]
                );
            } catch (e) {
                console.warn("Slip cleanup failed", e);
            }
        });

        // -----------------------------
        // BINDINGS (CRITICAL FIX)
        // -----------------------------
        this.handleAddLine = this.handleAddLine.bind(this);
        this.handleRemoveLine = this.handleRemoveLine.bind(this);

        this.confirm = useAsyncLockedMethod(this.confirm.bind(this));
    }

    // =========================================================
    // STATE INIT
    // =========================================================
    getInitialState() {
        const s = { payments: {} };

        if (this.props.default_cash_details) {
            s.payments[this.props.default_cash_details.id] = { counted: "0" };
        }

        (this.props.other_payment_methods || []).forEach((pm) => {
            if (pm?.id != null) {
                s.payments[pm.id] = { counted: "0" };
            }
        });

        return s;
    }

    // =========================================================
    // DIFFERENCES
    // =========================================================
    getDifference(id) {
        const pm = this._getPaymentMethod(id);
        const counted = parseFloat(this.state.payments[id]?.counted || 0);

        const linesTotal = this.getLinesTotal(id);
        const expected = pm?.amount || 0;

        return counted + linesTotal - expected;
    }

    getRestrictedDifference(id) {
        const pm = this._getPaymentMethod(id);
        const expected = pm?.breakdown?.restricted || 0;
        const actual = (this.state.lines[id]?.restricted || [])
            .reduce((a, l) => a + (l.amount || 0), 0);
        return actual - expected;
    }

    getUnrestrictedDifference(id) {
        const pm = this._getPaymentMethod(id);
        const expected = pm?.breakdown?.unrestricted || 0;
        const actual = (this.state.lines[id]?.unrestricted || [])
            .reduce((a, l) => a + (l.amount || 0), 0);
        return actual - expected;
    }

    getNeutralDifference(id) {
        const pm = this._getPaymentMethod(id);
        const expected = pm?.breakdown?.neutral || 0;
        const actual = (this.state.lines[id]?.neutral || [])
            .reduce((a, l) => a + (l.amount || 0), 0);
        return actual - expected;
    }

    getLinesTotal(id) {
        const l = this.state.lines[id] || {};
        return (
            (l.restricted || []).reduce((a, x) => a + (x.amount || 0), 0) +
            (l.unrestricted || []).reduce((a, x) => a + (x.amount || 0), 0) +
            (l.neutral || []).reduce((a, x) => a + (x.amount || 0), 0)
        );
    }

    formatCurrencyNeutral(v) {
        const n = Number(v);
        return this.env.utils.formatCurrency(Number.isFinite(n) ? n : 0);
    }

    // =========================================================
    // VALIDATION
    // =========================================================
    canConfirm() {
        return Object.values(this.state.payments).every((v) =>
            this.env.utils.isValidFloat(v.counted)
        );
    }

    // =========================================================
    // REQUIRED TEMPLATE FIX (YOUR ERROR FIX)
    // =========================================================
    shouldShowSlipHeaders() {
        return (
            this.shouldShowSlipInput(this.props.default_cash_details) ||
            (this.props.other_payment_methods || []).length > 0
        );
    }

    shouldShowSlipInput(pm) {
        return pm && !(pm.skip_amount_input === true || pm.skip_amount_input === "true");
    }

    // =========================================================
    // ADD / REMOVE LINES
    // =========================================================
    async handleAddLine(paymentId, type = "restricted") {
        const pm = this._getPaymentMethod(paymentId);
        const { amount, ref, bank } = this.state.newLines[paymentId][type];

        const num = parseFloat(amount);

        if (!pm?.skip_amount_input) {
            if (!ref || isNaN(num)) {
                return this.popup.add(ErrorPopup, {
                    title: _t("Invalid Input"),
                    body: _t("Amount and Ref required."),
                });
            }
        }

        const id = Date.now();

        const slip = await this.orm.call(
            "pos.session.slip",
            "create_session_slip",
            [
                this.pos.pos_session.id,
                {
                    payment_method_id: paymentId,
                    type,
                    amount: num,
                    ref,
                    bank_id: bank,
                },
            ]
        );

        if (slip?.status === "error") {
            return this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("Slip creation failed."),
            });
        }

        this.state.lines[paymentId][type].push({
            id,
            amount: num,
            ref,
            bank,
            record_id: slip.id,
        });

        this.state.newLines[paymentId][type] = {
            amount: 0,
            ref: "",
            bank: "",
        };
    }

    async handleRemoveLine(paymentId, lineId, record_id, type) {
        const res = await this.orm.call(
            "pos.session.slip",
            "delete_session_slip",
            [record_id]
        );

        if (res?.status !== "error") {
            this.state.lines[paymentId][type] =
                this.state.lines[paymentId][type].filter((l) => l.id !== lineId);
        }
    }

    // =========================================================
    // CLOSE SESSION (UNCHANGED LOGIC WRAPPED)
    // =========================================================
    async confirm() {
        return this.closeSession();
    }

    async closeSession() {
        try {
            const ok = await this.pos.push_orders_with_closing_popup();
            if (!ok) return;

            const bankDiffPairs = (this.props.other_payment_methods || [])
                .filter((p) => p.type === "bank")
                .map((p) => [p.id, this.getDifference(p.id)]);

            const response = await this.orm.call(
                "pos.session",
                "close_session_from_ui",
                [
                    this.pos.pos_session.id,
                    bankDiffPairs,
                    this.state.lines,
                ]
            );

            if (!response?.successful)  this.handleClosingError(response);

            this.pos.redirectToBackend();
        } catch (e) {
            if (e instanceof ConnectionLostError) throw e;

            await this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("Session closing failed."),
            });
        }
    }

    async cancel() {
        if (this.canCancel()) super.cancel();
    }

    canCancel() {
        return true;
    }
}