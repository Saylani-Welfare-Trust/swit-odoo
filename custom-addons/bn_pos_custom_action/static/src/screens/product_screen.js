/** @odoo-module **/
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

// 🔥 GLOBAL KEYBOARD EVENT LISTENER - WORKS AT THE TOP LEVEL
// This will capture the minus key press before any other handlers
document.addEventListener('keydown', function(e) {
    // Check for minus key (both regular keyboard and numpad)
    if (e.key === '-' || e.key === 'Minus' || e.key === 'Subtract') {
        console.log('Minus key detected globally!');

        // Check if we should block based on context
        // You can modify this condition if needed
        const shouldBlock = true; // Block for all products

        if (shouldBlock) {
            // Prevent the minus key from doing anything
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();

            // Show alert to user
            alert('Negative quantities are not allowed!');

            // Also try to clear any negative input
            setTimeout(() => {
                const activeElement = document.activeElement;
                if (activeElement && activeElement.tagName === 'INPUT') {
                    const value = activeElement.value;
                    if (value && value.startsWith('-')) {
                        activeElement.value = value.substring(1);
                        // Trigger input event to update the model
                        const inputEvent = new Event('input', { bubbles: true });
                        activeElement.dispatchEvent(inputEvent);
                    }
                }
            }, 10);

            return false;
        }
    }
}, true); // Use capture phase to intercept before any other handlers

// Now patch the ProductScreen
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

    // Hide returned product(s) from the product grid during a refund flow
    get productsToDisplay() {
        console.log('MY PATCH productsToDisplay CALLED', arguments);
        const products = super.productsToDisplay;
        const order = this.pos.get_order();
        if (!order) {
            return products;
        }

        const returnedProductIds = new Set(
            order
                .get_orderlines()
                .filter((line) => line.refunded_orderline_id)
                .map((line) => line.product.id)
        );

        console.log('Returned product IDs to hide:', [...returnedProductIds]);

        if (!returnedProductIds.size) {
            return products;
        }

        return products.filter((product) => !returnedProductIds.has(product.id));
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

        // Disable all buttons for welfare order except payment and custom action
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

        // DISABLE MINUS BUTTON FOR ALL PRODUCTS
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

    // Override the mounted lifecycle method to ensure event listeners are attached
    mounted() {
        // Call parent mounted if it exists
        if (super.mounted) {
            super.mounted();
        }

        // Setup keyboard event handler with multiple approaches
        this._setupKeyboardHandler();

        // Also intercept keydown at the document level with capture phase
        this._setupGlobalKeyHandler();
    },

    // Setup keyboard event listener with capture phase
    _setupGlobalKeyHandler() {
        // Remove existing global handler if any
        if (this._globalKeyHandler) {
            document.removeEventListener('keydown', this._globalKeyHandler, true);
        }

        this._globalKeyHandler = this._handleGlobalKeyEvent.bind(this);
        // Use capture phase (true) to intercept before other handlers
        document.addEventListener('keydown', this._globalKeyHandler, true);
        this._globalKeyBound = true;
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

    // Remove keyboard event listeners
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

    // Handle keyboard events at component level
    _handleKeyboardEvent(event) {
        // Check if minus key is pressed
        if (event.key === '-' || event.key === 'Minus' || event.key === 'Subtract') {
            // Always block negative entries for all products
            this._blockNegativeEntry(event);
        }
        return true;
    },

    // Handle keyboard events at global level with capture phase
    _handleGlobalKeyEvent(event) {
        // Check if minus key is pressed
        if (event.key === '-' || event.key === 'Minus' || event.key === 'Subtract') {
            // Always block negative entries for all products
            this._blockNegativeEntry(event);
        }
        return true;
    },

    // Block negative entry and show notification
    _blockNegativeEntry(event) {
        // Prevent default behavior
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        // Show notification to user
        this._showNegativeNotAllowedMessage();

        // Also try to clear any negative input
        this._clearNegativeInput();

        return false;
    },

    // Clear any negative input from the quantity field
    _clearNegativeInput() {
        try {
            // Check if there's an active input field
            const activeElement = document.activeElement;
            if (activeElement && activeElement.tagName === 'INPUT') {
                const value = activeElement.value;
                // If the value starts with '-', clear it or remove the minus sign
                if (value && value.startsWith('-')) {
                    activeElement.value = value.substring(1);
                    // Trigger input event to update the model
                    const inputEvent = new Event('input', { bubbles: true });
                    activeElement.dispatchEvent(inputEvent);
                }
            }

            // Also check for quantity input in the product screen
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

    // Show notification message when negative is not allowed
    _showNegativeNotAllowedMessage() {
        const message = _t("Negative quantity is not allowed. Please use positive quantities only.");

        // Try different notification methods
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
                // Use the global alert as fallback (already handled by top-level listener)
                console.log('Negative quantity blocked:', message);
            }
        } catch (error) {
            console.error('Error showing notification:', error);
            // Fallback to alert
            alert(message);
        }
    },

    // Clean up event listeners when component is destroyed
    destroy() {
        // Remove keyboard event listeners
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