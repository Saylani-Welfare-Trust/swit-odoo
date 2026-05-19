/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(ActionScreen.prototype, {
    get checkWelfareAccess() {
        return this.pos._welfare || false;
    },

    async clickRecordWF() {
        // First, ask if user wants to PAY or RETURN
        const { confirmed, payload: actionType } = await this.popup.add(
            SelectionPopup,
            {
                title: _t("Welfare Action"),
                list: [
                    { id: "pay", label: _t("💰 Pay (Disbursement)"), item: "pay" },
                    { id: "return", label: _t("🔄 Return (Money Back)"), item: "return" },
                ],
            },
        );

        if (!confirmed) return;

        if (actionType === 'pay') {
            // PAY LOGIC - One Time or Recurring
            await this.handleWelfarePay();
        } 
        else if (actionType === 'return') {
            // RETURN LOGIC - One Time or Recurring
            await this.handleWelfareReturn();
        }
    },

    async handleWelfarePay() {
        const { confirmed, payload: selectedOption } = await this.popup.add(
            SelectionPopup,
            {
                title: _t("Select Disbursement Type"),
                list: [
                    { id: "0", label: _t("One Time"), item: "one_time" },
                    { id: "1", label: _t("Recurring"), item: "recurring" },
                ],
            },
        );

        if (confirmed) {
            if (selectedOption === 'one_time') {
                this.popup.add(ReceivingPopup, {
                    title: "Disbursement Number",
                    placeholder: "WF/XX/XXXXX",
                    action_type: "wf",
                    wf_request_type: "one_time"
                });
            } else {
                this.popup.add(ReceivingPopup, {
                    title: "Disbursement Number",
                    placeholder: "WF/XX/XXXXX",
                    action_type: "wf",
                    wf_request_type: "recurring"
                });
            }
        }
    },

    async handleWelfareReturn() {
        // First, ask for Return Type (One Time or Recurring)
        const { confirmed, payload: returnType } = await this.popup.add(
            SelectionPopup,
            {
                title: _t("Select Return Type"),
                list: [
                    { id: "one_time", label: _t("One Time Return"), item: "one_time" },
                    { id: "recurring", label: _t("Recurring Return"), item: "recurring" },
                ],
            },
        );

        if (!confirmed) return;

        // Ask for Welfare Form Number
        const { confirmed: confirmedNumber, payload: welfareNumber } = await this.popup.add(
            ReceivingPopup,
            {
                title: _t("Welfare Return"),
                placeholder: "Enter Welfare Form Number (e.g., WF-2024-001)",
                action_type: "wf_return",
            }
        );

        if (confirmedNumber && welfareNumber) {
            if (returnType === 'one_time') {
                await this.processOneTimeReturn(welfareNumber);
            } else {
                await this.processRecurringReturn(welfareNumber);
            }
        }
    },

    async processOneTimeReturn(welfareNumber) {
        try {
            // Search for eligible one-time welfare lines
            const lines = await this.env.services.orm.call(
                'welfare.line',
                'search_read',
                [[
                    ['welfare_id.name', '=', welfareNumber],
                    ['payment_type', '=', 'assigned_officer'],
                    ['state', '=', 'collected'],
                    ['welfare_id.order_type', '=', 'one_time']
                ]],
                { fields: ['id', 'product_id', 'total_amount', 'quantity', 'welfare_id'] }
            );

            if (lines.length === 0) {
                await this.popup.add(SelectionPopup, {
                    title: _t("No Eligible Lines"),
                    list: [{ id: "ok", label: _t(`No collected Marfat lines found for ${welfareNumber}`), item: "ok" }],
                });
                return;
            }

            // Add return lines to order
            for (const line of lines) {
                const product = this.pos.db.product_by_id(line.product_id[0]);
                if (product) {
                    this.pos.get_order().add_product(product, {
                        quantity: line.quantity,
                        price: line.total_amount / line.quantity,
                        extras: {
                            is_welfare_return: true,
                            welfare_number: welfareNumber,
                            welfare_line_id: line.id,
                            return_type: 'one_time'
                        }
                    });
                }
            }

            const totalAmount = lines.reduce((sum, l) => sum + l.total_amount, 0);
            
            await this.popup.add(SelectionPopup, {
                title: _t("One Time Return Lines Added"),
                list: [
                    { 
                        id: "ok", 
                        label: _t(`Added ${lines.length} line(s). Total Return Amount: ${totalAmount}`), 
                        item: "ok" 
                    }
                ],
            });

        } catch (error) {
            console.error("One Time Return Error:", error);
            await this.popup.add(SelectionPopup, {
                title: _t("Error"),
                list: [{ id: "ok", label: _t(`Error: ${error.message}`), item: "ok" }],
            });
        }
    },

    async processRecurringReturn(welfareNumber) {
        try {
            // Search for eligible recurring welfare lines
            const lines = await this.env.services.orm.call(
                'welfare.recurring.line',
                'search_read',
                [[
                    ['welfare_id.name', '=', welfareNumber],
                    ['payment_type', '=', 'assigned_officer'],
                    ['state', '=', 'collected'],
                    ['welfare_id.order_type', '=', 'recurring']
                ]],
                { fields: ['id', 'product_id', 'total_amount', 'quantity', 'welfare_id'] }
            );

            if (lines.length === 0) {
                await this.popup.add(SelectionPopup, {
                    title: _t("No Eligible Lines"),
                    list: [{ id: "ok", label: _t(`No collected recurring Marfat lines found for ${welfareNumber}`), item: "ok" }],
                });
                return;
            }

            // Add recurring return lines to order
            for (const line of lines) {
                const product = this.pos.db.product_by_id(line.product_id[0]);
                if (product) {
                    this.pos.get_order().add_product(product, {
                        quantity: line.quantity,
                        price: line.total_amount / line.quantity,
                        extras: {
                            is_welfare_return: true,
                            welfare_number: welfareNumber,
                            welfare_line_id: line.id,
                            return_type: 'recurring',
                            is_recurring_return: true
                        }
                    });
                }
            }

            const totalAmount = lines.reduce((sum, l) => sum + l.total_amount, 0);
            
            await this.popup.add(SelectionPopup, {
                title: _t("Recurring Return Lines Added"),
                list: [
                    { 
                        id: "ok", 
                        label: _t(`Added ${lines.length} recurring line(s). Total Return Amount: ${totalAmount}`), 
                        item: "ok" 
                    }
                ],
            });

        } catch (error) {
            console.error("Recurring Return Error:", error);
            await this.popup.add(SelectionPopup, {
                title: _t("Error"),
                list: [{ id: "ok", label: _t(`Error: ${error.message}`), item: "ok" }],
            });
        }
    },
});