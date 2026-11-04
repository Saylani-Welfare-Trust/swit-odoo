/** @odoo-module */

import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

/**
 * Due this month: lines are paid in the month of their collection date
 */
function isDueThisMonth(line) {
    if (!line.collection_date) {
        return false;
    }
    const [year, month] = line.collection_date.split("-").map(Number);
    const now = new Date();
    return year === now.getFullYear() && month - 1 === now.getMonth();
}

function groupByProduct(lines, amountField) {
    const grouped = {};
    for (const line of lines) {
        const productId = line.product_id && line.product_id[0];
        if (!productId) {
            continue;
        }
        grouped[productId] = grouped[productId] || { quantity: 0, amount: 0, lines: [] };
        grouped[productId].quantity += line.quantity || 1;
        grouped[productId].amount += line[amountField] || 0;
        grouped[productId].lines.push(line);
    }
    return Object.values(grouped);
}

patch(ReceivingPopup.prototype, {
    async confirm() {
        if (this.props.action_type === "sj_return" && this.state.record_number) {
            this.props.resolve({ confirmed: true, payload: this.state.record_number });
            this.cancel();
            return;
        }
        if (this.props.action_type === "sj" && this.state.record_number) {
            const selectedOrder = this.pos.get_order();
            selectedOrder.set_receive_voucher(true);
            await this.processSadqaJariyaRecord(selectedOrder);
            this.cancel();
            return;
        }
        return super.confirm(...arguments);
    },

    /**
     * Adds the lines of an approved application due this month, paid with the configured product
     */
    async processSadqaJariyaRecord(selectedOrder) {
        const isRecurring = this.wf_request_type === "recurring";
        try {
            if (selectedOrder.extra_data?.sadqa_jariya?.disbursement_status === "pending") {
                this.notification.add(_t("A Sadqa e Jariya payment is already loaded on this order."), { type: "warning" });
                return;
            }
            const records = await this.orm.searchRead(
                "sadqa.jariya",
                [["name", "=", this.state.record_number]],
                ["id", "name", "state", "donee_id", "order_type"],
                { limit: 1 }
            );
            if (!records.length) {
                return this.handleRecordNotFound();
            }
            const application = records[0];
            // One-time: Approved, or Final Approval to pay only the HOD lines; recurring: Recurring
            const allowedStates = isRecurring ? ["recurring"] : ["approve", "mem_approve"];
            if (!allowedStates.includes(application.state)) {
                this.notification.add(
                    _t("Unauthorized Request State: %s. Expected %s.", application.state, allowedStates.join(" / ")),
                    { type: "warning" }
                );
                return;
            }

            const productName = this.pos.company.sadqa_jariya_pos_product;
            const products = productName ? await this.orm.searchRead(
                "product.product",
                [["name", "=", productName], ["detailed_type", "=", "service"], ["available_in_pos", "=", true]],
                ["id"],
                { limit: 1 }
            ) : [];
            const configuredProduct = products.length && this.pos.db.get_product_by_id(products[0].id);
            if (!configuredProduct) {
                await this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: _t("Set the Sadqa e Jariya POS Product in the Company settings (a service product available in POS, loaded in this session)."),
                });
                return;
            }

            const lineModel = isRecurring ? "sadqa.jariya.recurring.line" : "sadqa.jariya.line";
            const amountField = isRecurring ? "amount" : "total_amount";
            const lines = await this.orm.searchRead(
                lineModel,
                [
                    ["application_id", "=", application.id],
                    ["state", "=", "draft"],
                    ["disbursement_category_id.name", "=", "Cash"],
                    ["collection_point", "=", "branch"],
                ],
                ["id", "product_id", amountField, "quantity", "collection_date"].concat(isRecurring ? [] : ["is_hod"])
            );
            // HOD lines can be paid from Final Approval on, the other one-time lines once approved
            const dueLines = lines.filter((line) =>
                isDueThisMonth(line) && (isRecurring || line.is_hod || application.state === "approve")
            );
            if (!dueLines.length) {
                this.notification.add(_t("No Sadqa e Jariya lines due this month"), { type: "warning" });
                return;
            }

            const payLines = [];
            for (const group of groupByProduct(dueLines.filter((line) => !line.is_hod), amountField)) {
                selectedOrder.add_product(configuredProduct, {
                    quantity: -1 * group.quantity,
                    price_extra: group.amount / group.quantity - configuredProduct.lst_price,
                });
                for (const line of group.lines) {
                    payLines.push({ id: line.id, amount: line[amountField] || 0 });
                }
            }
            // Each HOD line gets its own order line, named after its product, so the cashier can delete it
            for (const line of dueLines.filter((line) => line.is_hod)) {
                const quantity = line.quantity || 1;
                await selectedOrder.add_product(configuredProduct, {
                    quantity: -1 * quantity,
                    price_extra: line[amountField] / quantity - configuredProduct.lst_price,
                    merge: false,
                    extras: { sadqa_jariya_hod_line_id: line.id },
                });
                selectedOrder.get_selected_orderline().full_product_name = `${configuredProduct.display_name} - ${line.product_id[1]}`;
                payLines.push({ id: line.id, amount: line[amountField], is_hod: true });
            }

            if (application.donee_id) {
                const partner = await this.getOrLoadPartner(application.donee_id[0]);
                if (partner) {
                    this.assignPartnerToOrder(partner, selectedOrder);
                }
            }
            selectedOrder.extra_data = selectedOrder.extra_data || {};
            selectedOrder.extra_data.sadqa_jariya = {
                record_number: application.name,
                application_id: application.id,
                is_recurring: isRecurring,
                line_model: lineModel,
                line_ids: payLines,
                disbursement_status: "pending",
                total_disbursed_amount: 0,
                scan_timestamp: new Date().toISOString(),
            };
            this.notification.add(_t("Added %s Sadqa e Jariya line(s)", payLines.length), { type: "success" });
        } catch (error) {
            this.handleProcessingError(error);
        }
    },
});
