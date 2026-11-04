/** @odoo-module **/
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";


patch(ProductScreen.prototype, {
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
    
    get isWelfareOrder() {
        const order = this.pos.get_order();
        return order && order.extra_data && order.extra_data.welfare;
    },

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

        if (this.isWelfareOrder) {
            // Disable all except payment and custom action (adjust value as needed)
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

        //  DISABLE MINUS BUTTON FOR ALL PRODUCTS
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
        
        return buttons.map((button) => ({
            ...button,
            class: this.pos.numpadMode === button.value ? "active border-primary" : "",
        }));
    }
})