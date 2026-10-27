/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

// Welfare disbursements (money out) and returns (money back) at the POS.
// The lines are checked on the server before the payment is validated, and
// updated once the order is saved: a failed or cancelled validation leaves
// them untouched.
patch(PaymentScreen.prototype, {
    _welfarePayment(order) {
        const wf = order && order.extra_data && order.extra_data.welfare;
        if (!wf || wf.is_welfare_order !== true || wf.disbursement_status === 'completed') {
            return null;
        }
        const lines = (wf.is_recurring ? wf.recurring_line_ids : wf.welfare_line_ids) || [];
        return {
            data: wf,
            model: wf.is_recurring ? 'welfare.recurring.line' : 'welfare.line',
            ids: lines.map((l) => l.id).filter(Boolean),
        };
    },

    _welfareReturns(order) {
        const returns = [];
        const seen = new Set();
        const add = (model, id, number, type) => {
            const key = `${model}-${id}`;
            if (id && !seen.has(key)) {
                seen.add(key);
                returns.push({ model, id, number: number || '', type: type || 'one_time' });
            }
        };
        const data = order && order.extra_data && order.extra_data.welfare_return;
        if (data && data.status !== 'completed') {
            const model = data.line_model || (data.return_type === 'recurring' ? 'welfare.recurring.line' : 'welfare.line');
            for (const line of data.line_ids || []) {
                add(model, line.id, data.record_number, data.return_type);
            }
        }
        for (const line of order ? order.get_orderlines() : []) {
            const extras = line.get_extras ? line.get_extras() : {};
            if (extras && extras.is_welfare_return === true) {
                add(extras.return_type === 'recurring' ? 'welfare.recurring.line' : 'welfare.line',
                    extras.welfare_line_id, extras.welfare_number, extras.return_type);
            }
        }
        return returns;
    },

    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const payment = this._welfarePayment(order);
        const returns = this._welfareReturns(order);

        if (payment && payment.ids.length) {
            try {
                await this.env.services.orm.call(payment.model, 'pos_check_payable', [payment.ids]);
            } catch (error) {
                await this.popup.add(ErrorPopup, {
                    title: _t("Welfare Payment Blocked"),
                    body: (error.data && error.data.message) || error.message || _t("This welfare payment cannot be processed."),
                });
                return;
            }
            order.set_source_document(payment.data.record_number);
        }

        for (const ret of returns) {
            const [line] = await this.env.services.orm.read(ret.model, [ret.id], ['state', 'payment_type']);
            if (!line || line.state !== 'pending' || line.payment_type !== 'assigned_officer') {
                await this.popup.add(ErrorPopup, {
                    title: _t("Welfare Return Blocked"),
                    body: `Welfare ${ret.number}: only pending Marfat lines can be returned.`,
                });
                return;
            }
        }

        const result = await super.validateOrder(...arguments);
        if (!order.finalized || (!(payment && payment.ids.length) && !returns.length)) {
            return result;
        }
        const notify = (message, type) => this.env.services.notification.add(message, { type, sticky: type === 'danger' });
        if (payment && payment.ids.length) {
            try {
                await this.env.services.orm.call(payment.model, 'action_disbursed', [payment.ids]);
                payment.data.disbursement_status = 'completed';
                notify(`Welfare ${payment.data.record_number} disbursement completed.`, 'success');
            } catch (error) {
                console.error("Welfare disbursement:", error);
                notify(`Order ${order.name} is saved, but welfare ${payment.data.record_number} was not marked disbursed. Please inform the Welfare team.`, 'danger');
            }
        }
        for (const ret of returns) {
            try {
                await this.env.services.orm.call(ret.model, 'action_return_to_pos', [[ret.id]]);
                notify(`${ret.type === 'recurring' ? 'Recurring' : 'One Time'} Welfare return processed: ${ret.number}`, 'success');
            } catch (error) {
                console.error("Welfare return:", error);
                notify(`Order ${order.name} is saved, but the return of welfare ${ret.number} was not recorded. Please inform the Welfare team.`, 'danger');
            }
        }
        const returnData = order.extra_data && order.extra_data.welfare_return;
        if (returnData && returns.length) {
            returnData.status = 'completed';
        }
        return result;
    },
});
