/** @odoo-module **/
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

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
            { value: "-", text: "+/-" ,disabled: !this.pos.config.allow_negative_quantity},
            { value: "0" },
            { value: this.env.services.localization.decimalPoint },
            { value: "Backspace", text: "⌫" },
        ];

        // Disable all buttons for welfare order except payment and custom action
        if (this.isWelfareOrder) {
            return buttons.map(btn => {
                if (["payment", "custom_action"].includes(btn.value)) {
                    return { ...btn, disabled: false };
                }
                return { ...btn, disabled: true };
            });
        }

        // 🔥 DISABLE MINUS BUTTON FOR ALL PRODUCTS
        // Disable the minus button regardless of product type
        return buttons.map(button => {
            if (button.value === "-") {
                // Always disable the minus button for all products
                return { ...button, disabled: true };
            }
            
            // Apply active class for numpad mode
            return {
                ...button,
                class: this.pos.numpadMode === button.value ? "active border-primary" : "",
            };
        });
    },

    // Initialize component and setup keyboard event handling
    init() {
        // Call parent init if it exists
        if (super.init) {
            super.init();
        }

        // Setup keyboard event handler
        this._setupKeyboardHandler();
    },

    // Setup keyboard event listener
    _setupKeyboardHandler() {
        // Remove any existing listener to prevent duplicates
        if (this._keyboardBound) {
            document.removeEventListener('keydown', this._keyboardHandler);
        }

        // Bind the keyboard event handler
        this._keyboardHandler = this._handleKeyboardEvent.bind(this);
        document.addEventListener('keydown', this._keyboardHandler);
        this._keyboardBound = true;
    },

    // Remove keyboard event listener
    _removeKeyboardHandler() {
        if (this._keyboardHandler && this._keyboardBound) {
            document.removeEventListener('keydown', this._keyboardHandler);
            this._keyboardBound = false;
        }
    },

    // Handle keyboard events
    _handleKeyboardEvent(event) {
        // Check if minus key is pressed (both main keyboard and numpad)
        if (event.key === '-' || event.key === 'Minus' || event.key === 'Subtract') {
            // 🔥 BLOCK NEGATIVE ENTRIES FOR ALL PRODUCTS
            // Always block negative entries regardless of product type
            const shouldBlockNegative = true; // Always block for all products
            
            if (shouldBlockNegative) {
                // Prevent default behavior and stop propagation
                event.preventDefault();
                event.stopPropagation();
                
                // Show notification to user
                this._showNegativeNotAllowedMessage();
                return false;
            }
        }
        return true;
    },

    // Show notification message when negative is not allowed
    _showNegativeNotAllowedMessage() {
        const message = _t("Negative quantity is not allowed. Please use positive quantities only.");
        
        // Try different notification methods based on what's available
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
                // Fallback to console warning
                console.warn('Negative quantity blocked:', message);
                // Also try to show in UI if possible
                const display = this.el?.querySelector?.('.pos-screen');
                if (display) {
                    const notification = document.createElement('div');
                    notification.className = 'alert alert-warning';
                    notification.textContent = message;
                    notification.style.cssText = 'position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 9999; padding: 20px; background: #fff3cd; border: 1px solid #ffeeba; border-radius: 4px; box-shadow: 0 0 10px rgba(0,0,0,0.3);';
                    document.body.appendChild(notification);
                    setTimeout(() => notification.remove(), 3000);
                }
            }
        } catch (error) {
            console.error('Error showing notification:', error);
        }
    },

    // Clean up event listeners when component is destroyed
    destroy() {
        // Remove keyboard event listener
        this._removeKeyboardHandler();
        
        // Call parent destroy if it exists
        if (super.destroy) {
            super.destroy();
        }
    },

    // Helper to check if minus button should be disabled (always true now)
    get isMinusDisabled() {
        return true; // Always disabled for all products
    }
});