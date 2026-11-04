/** @odoo-module */

import { onWillStart } from "@odoo/owl";
import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

const LINE_MODELS = {
    one_time: "sadqa.jariya.line",
    recurring: "sadqa.jariya.recurring.line",
};

patch(ActionScreen.prototype, {
    setup() {
        super.setup(...arguments);
        onWillStart(async () => {
            this.sadqaJariyaAccess = await this.env.services.user.hasGroup(
                "bn_sadqa_e_jariya.group_sadqa_jariya_pos_action"
            );
        });
    },

    async clickRecordSJ() {
        const { confirmed, payload: actionType } = await this.popup.add(SelectionPopup, {
            title: _t("Sadqa e Jariya Action"),
            list: [
                { id: "pay", label: _t("💰 Pay (Disbursement)"), item: "pay" },
                { id: "return", label: _t("🔄 Return (Money Back)"), item: "return" },
            ],
        });
        if (!confirmed) {
            return;
        }
        const { confirmed: typeConfirmed, payload: requestType } = await this.popup.add(SelectionPopup, {
            title: actionType === "pay" ? _t("Select Disbursement Type") : _t("Select Return Type"),
            list: [
                { id: "one_time", label: _t("One Time"), item: "one_time" },
                { id: "recurring", label: _t("Recurring"), item: "recurring" },
            ],
        });
        if (!typeConfirmed) {
            return;
        }
        if (actionType === "pay") {
            this.popup.add(ReceivingPopup, {
                title: _t("Sadqa e Jariya Number"),
                placeholder: "INS/XXXX/XXXX",
                action_type: "sj",
                wf_request_type: requestType,
            });
            // the Actions popup would stay over the order
            this.cancel();
            return;
        }
        const { confirmed: numberConfirmed, payload: number } = await this.popup.add(ReceivingPopup, {
            title: _t("Sadqa e Jariya Return"),
            placeholder: "INS/XXXX/XXXX",
            action_type: "sj_return",
        });
        if (numberConfirmed && number) {
            await this.processSadqaJariyaReturn(number, requestType);
            this.cancel();
        }
    },

    /**
     * Pending Assigned Officer (Marfat) lines brought back by the donee
     */
    async processSadqaJariyaReturn(number, returnType) {
        const order = this.pos.get_order();
        if (order.extra_data?.sadqa_jariya_return?.status === "pending") {
            this.notification.add(_t("A Sadqa e Jariya return is already loaded on this order."), { type: "warning" });
            return;
        }
        const lineModel = LINE_MODELS[returnType];
        const amountField = returnType === "recurring" ? "amount" : "total_amount";
        try {
            const lines = await this.orm.searchRead(
                lineModel,
                [
                    ["application_id.name", "=", number],
                    ["payment_type", "=", "assigned_officer"],
                    ["state", "=", "pending"],
                    ["application_id.order_type", "=", returnType],
                ],
                ["id", "product_id", amountField, "quantity", "donee_id"]
            );
            if (!lines.length) {
                this.notification.add(_t("No pending Marfat lines found for %s", number), { type: "warning" });
                return;
            }
            const doneeId = lines[0].donee_id && lines[0].donee_id[0];
            if (doneeId) {
                let partner = this.pos.db.get_partner_by_id(doneeId);
                if (!partner) {
                    const partners = await this.orm.searchRead("res.partner", [["id", "=", doneeId]], ["id", "name", "phone", "email"]);
                    this.pos.db.add_partners(partners);
                    partner = this.pos.db.get_partner_by_id(doneeId);
                }
                if (partner) {
                    order.set_partner(partner);
                }
            }
            for (const line of lines) {
                const product = this.pos.db.get_product_by_id(line.product_id[0]);
                if (product) {
                    order.add_product(product, {
                        quantity: line.quantity,
                        price: line[amountField] / (line.quantity || 1),
                        merge: false,
                    });
                }
            }
            order.extra_data = order.extra_data || {};
            order.extra_data.sadqa_jariya_return = {
                record_number: number,
                return_type: returnType,
                line_model: lineModel,
                line_ids: lines.map((line) => line.id),
                status: "pending",
            };
            const total = lines.reduce((sum, line) => sum + (line[amountField] || 0), 0);
            this.notification.add(_t("Added %s line(s). Total Return Amount: %s", lines.length, total), { type: "success" });
        } catch (error) {
            console.error("Sadqa e Jariya Return Error:", error);
            this.notification.add(_t("Error: %s", error.message || error), { type: "danger" });
        }
    },
});
