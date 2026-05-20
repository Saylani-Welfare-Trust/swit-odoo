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
                restricted: { bank: "0", amount: "0", ref: "", record_id: 0 },
                unrestricted: { bank: "0", amount: "0", ref: "", record_id: 0 },
                neutral: { bank: "0", amount: "0", ref: "", record_id: 0 },
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

    async handleAddLine(paymentId, type = "restricted") {
        const pm = this._getPaymentMethod(paymentId);
        const { amount, ref, bank } = this.state.newLines[paymentId][type];
        const numAmount = parseFloat(amount);
        const isBankInvalid = !bank || bank === "0";
        const isAmountInvalid = isNaN(numAmount);

        if (this.shouldShowSlipInput(pm) && (!ref || isAmountInvalid || isBankInvalid)) {
            this.popup.add(ErrorPopup, {
                title: _t("Invalid Input"),
                body: _t("Amount and Reference are required."),
            });
            return;
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
            this.popup.add(ErrorPopup, { title: _t("Error"), body: _t("Slip creation failed.") });
            return;
        }

        this.state.lines[paymentId][type].push({
            id: Date.now(),
            amount: numAmount || 0,
            ref: ref || "",
            bank: bank,
            record_id: slip.id,
        });

        this.state.newLines[paymentId][type] = { bank: "0", amount: "0", ref: "", record_id: 0 };
    }

    async handleRemoveLine(paymentId, lineId, recordId, type) {
        const res = await this.orm.call("pos.session.slip", "delete_session_slip", [recordId]);
        if (res?.status !== "error") {
            this.state.lines[paymentId][type] = this.state.lines[paymentId][type].filter((l) => l.id !== lineId);
        }
    }

    canConfirm() {
        return Object.values(this.state.payments).every((v) => this.env.utils.isValidFloat(v.counted));
    }

    canCancel() {
        return true;
    }

    async confirm() {
        for (const pm of (this.props.other_payment_methods || [])) {

            if (pm.type !== "bank") {
                continue;
            }

            const difference = this.getDifference(pm.id);

            // ONLY VALIDATE IF DIFFERENCE IS NOT ZERO
            if (difference !== 0) {

                const lines = this.state.lines[pm.id] || {};

                const allLines = [
                    ...(lines.restricted || []),
                    ...(lines.unrestricted || []),
                    ...(lines.neutral || []),
                ];

                // NO LINE ADDED
                if (!allLines.length) {

                    await this.popup.add(ErrorPopup, {
                        title: _t("Validation Error"),
                        body: _t(
                            `Payment method "${pm.name}" has a difference. Please add at least one slip line.`
                        ),
                    });

                    return;
                }

                // BANK NOT SELECTED
                const invalidBank = allLines.some(
                    (line) =>
                        !line.bank ||
                        line.bank === "0" ||
                        line.bank === 0
                );

                if (invalidBank) {

                    await this.popup.add(ErrorPopup, {
                        title: _t("Validation Error"),
                        body: _t(
                            `Please select a bank for all slip lines of "${pm.name}".`
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
            .filter((p) => p.type === "bank")
            .map((p) => [p.id, this.getDifference(p.id)]);

        const response = await this.orm.call("pos.session", "close_session_from_ui", [
            this.pos.pos_session.id,
            bankDiffPairs,
            this.state.lines,
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