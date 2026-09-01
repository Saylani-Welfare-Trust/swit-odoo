/** @odoo-module **/
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

// 🔥 GLOBAL KEYBOARD EVENT LISTENER - WORKS AT THE TOP LEVEL
document.addEventListener('keydown', function(e) {
    if (e.key === '-' || e.key === 'Minus' || e.key === 'Subtract') {
        console.log('Minus key detected globally!');
        const shouldBlock = true;
        if (shouldBlock) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            alert('Negative quantities are not allowed!');
            setTimeout(() => {
                const activeElement = document.activeElement;
                if (activeElement && activeElement.tagName === 'INPUT') {
                    const value = activeElement.value;
                    if (value && value.startsWith('-')) {
                        activeElement.value = value.substring(1);
                        const inputEvent = new Event('input', { bubbles: true });
                        activeElement.dispatchEvent(inputEvent);
                    }
                }
            }, 10);
            return false;
        }
    }
}, true);

patch(ProductScreen.prototype, {
    // Getter to check if order has Qurbani product
    get hasQurbaniProduct() {
        const currentOrder = this.pos.get_order();
        if (!currentOrder) return false;

        return currentOrder.get_orderlines().some(line => {
            const product = line.product;

            return (
                product.is_livestock &&
                product.detailed_type === "product" &&
                product.categ?.name?.toLowerCase().includes("qurbani")
            );
        });
    },

    // Getter to check if order is welfare order
    get isWelfareOrder() {
        const order = this.pos.get_order();
        return order && order.extra_data && order.extra_data.welfare;
    },

    // 🆕 Return/refund lines ko order-list se hide karne ke liye
    getVisibleOrderlines() {
        const order = this.pos.get_order();
        if (!order) {
            return [];
        }
        return order.orderlines.filter((line) => !line.refunded_orderline_id);
    },

    // 🆕 Sirf visible (non-return) lines ka total — display ke liye
    getVisibleOrderTotal() {
        const lines = this.getVisibleOrderlines();
        return lines.reduce((sum, line) => sum + line.get_price_with_tax(), 0);
    },

    // 🆕 Sirf visible (non-return) lines ka tax — display ke liye
    getVisibleOrderTax() {
        const lines = this.getVisibleOrderlines();
        return lines.reduce((sum, line) => sum + line.get_tax(), 0);
    },

    // Override numpad buttons to disable based on conditions
    getNumpadButtons() {
        const buttons = [
            { value: "1" },
            { value: "2" },
            { value: "3" },
            { value: "quantity", text: _t("Qty") },
            { value: "4" },
            { value: "5" },
            { value: "6" },
            { value: "discount", text: _t("% Disc"), disabled: !this.pos.config.manual_discount },
            { value: "7" },
            { value: "8" },
            { value: "9" },
            {
                value: "price",
                text: _t("Price"),
                disabled: !this.pos.cashierHasPriceControlRights(),
            },
            { value: "-", text: "+/-", disabled: !this.pos.config.allow_negative_quantity },
            { value: "0" },
            { value: this.env.services.localization.decimalPoint },
            { value: "Backspace", text: "⌫" },
        ];

        if (this.isWelfareOrder) {
            return buttons.map(btn => {
                if (["payment", "custom_action"].includes(btn.value)) {
                    return { ...btn, disabled: false };
                }
                return { ...btn, disabled: true };
            });
        }

        const order = this.pos.get_order();
        const selectedLine = order?.get_selected_orderline?.() || order?.get_orderlines?.().slice(-1)[0] || null;
        const isSelectedDonationInKind = !!selectedLine && !!selectedLine.product && !!selectedLine.product.is_donation_in_kind;

        return buttons.map(button => {
            if (button.value === "price" && isSelectedDonationInKind) {
                return { ...button, disabled: true };
            }
            if (button.value === "-") {
                return { ...button, disabled: true };
            }

            return {
                ...button,
                class: this.pos.numpadMode === button.value ? "active border-primary" : "",
            };
        });
    },

    mounted() {
        if (super.mounted) {
            super.mounted();
        }
        this._setupKeyboardHandler();
        this._setupGlobalKeyHandler();
    },

    _setupGlobalKeyHandler() {
        if (this._globalKeyHandler) {
            document.removeEventListener('keydown', this._globalKeyHandler, true);
        }
        this._globalKeyHandler = this._handleGlobalKeyEvent.bind(this);
        document.addEventListener('keydown', this._globalKeyHandler, true);
        this._globalKeyBound = true;
    },

    _setupKeyboardHandler() {
        if (this._keyboardBound) {
            document.removeEventListener('keydown', this._keyboardHandler);
        }
        this._keyboardHandler = this._handleKeyboardEvent.bind(this);
        document.addEventListener('keydown', this._keyboardHandler);
        this._keyboardBound = true;
    },

    _removeKeyboardHandler() {
        if (this._keyboardHandler && this._keyboardBound) {
            document.removeEventListener('keydown', this._keyboardHandler);
            this._keyboardBound = false;
        }
        if (this._globalKeyHandler && this._globalKeyBound) {
            document.removeEventListener('keydown', this._globalKeyHandler, true);
            this._globalKeyBound = false;
        }
    },

    _handleKeyboardEvent(event) {
        if (event.key === '-' || event.key === 'Minus' || event.key === 'Subtract') {
            this._blockNegativeEntry(event);
        }
        return true;
    },

    _handleGlobalKeyEvent(event) {
        if (event.key === '-' || event.key === 'Minus' || event.key === 'Subtract') {
            this._blockNegativeEntry(event);
        }
        return true;
    },

    _blockNegativeEntry(event) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        this._showNegativeNotAllowedMessage();
        this._clearNegativeInput();
        return false;
    },

    _clearNegativeInput() {
        try {
            const activeElement = document.activeElement;
            if (activeElement && activeElement.tagName === 'INPUT') {
                const value = activeElement.value;
                if (value && value.startsWith('-')) {
                    activeElement.value = value.substring(1);
                    const inputEvent = new Event('input', { bubbles: true });
                    activeElement.dispatchEvent(inputEvent);
                }
            }
            const quantityInput = this.el?.querySelector?.('input[data-field="quantity"]');
            if (quantityInput && quantityInput.value && quantityInput.value.startsWith('-')) {
                quantityInput.value = quantityInput.value.substring(1);
                const inputEvent = new Event('input', { bubbles: true });
                quantityInput.dispatchEvent(inputEvent);
            }
        } catch (error) {
            console.debug('Error clearing negative input:', error);
        }
    },

    _showNegativeNotAllowedMessage() {
        const message = _t("Negative quantity is not allowed. Please use positive quantities only.");
        try {
            if (this.notification) {
                this.notification.add(message, { type: 'warning' });
            } else if (this.pos?.notification) {
                this.pos.notification.add(message, { type: 'warning' });
            } else if (this.env?.services?.notification) {
                this.env.services.notification.add(message, { type: 'warning' });
            } else if (this.env?.services?.alert) {
                this.env.services.alert(message);
            } else {
                console.log('Negative quantity blocked:', message);
            }
        } catch (error) {
            console.error('Error showing notification:', error);
            alert(message);
        }
    },

    destroy() {
        this._removeKeyboardHandler();
        if (super.destroy) {
            super.destroy();
        }
    },

    get isMinusDisabled() {
        return true;
    }
});