/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { ConnectionLostError, ConnectionAbortedError } from "@web/core/network/rpc_service";

import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";
import { Component, useState, useEffect, useRef } from "@odoo/owl";
import { OfflineErrorPopup } from "@point_of_sale/app/errors/popups/offline_error_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ProductInfoPopup } from "@point_of_sale/app/screens/product_screen/product_info_popup/product_info_popup";
import { CategoryStockMoveSelector } from "@sm_point_of_sale_apps/js/CustomCategorySelector/CategoryStockMoveSelector";
import { Input } from "@point_of_sale/app/generic_components/inputs/input/input";

export class ProductStockMoveScreenList extends Component {
    static components = { ProductCard, CategoryStockMoveSelector, Input };
    static template = "sm_point_of_sale_apps.ProductStockMoveScreenList";
    setup() {
        this.state = useState({
            previousSearchWord: "",
            currentOffset: 0,
            loadingDemo: false,
            height: 0,
        });
        this.productsWidgetRef = useRef("products-widget");
        this.pos = usePos();
        this.ui = useState(useService("ui"));
        this.popup = useService("popup");
        this.notification = useService("pos_notification");
        this.orm = useService("orm");
        useEffect(() => {
            const productsWidget = this.productsWidgetRef.el;
            if (!productsWidget) {
                return;
            }
            const observer = new ResizeObserver((entries) => {
                if (!entries.length) {
                    return;
                }
                const height = entries[0].contentRect.height;
                this.state.height = height;
            });
            observer.observe(productsWidget);
            return () => observer.disconnect();
        });
    }

    getShowCategoryImages() {
        return (
            this.pos.show_category_images &&
            Object.values(this.pos.db.category_by_id).some((category) => category.has_image) &&
            !this.ui.isSmall
        );
    }

    /**
     * @returns {import("@point_of_sale/app/generic_components/category_selector/category_selector").Category[]}
     */
    getCategories() {
        return [
            ...this.pos.db.get_category_ancestors_ids(this.pos.selectedStockMoveCategoryId),
            this.pos.selectedStockMoveCategoryId,
            ...this.pos.db.get_category_childs_ids(this.pos.selectedStockMoveCategoryId),
        ]
            .map((id) => this.pos.db.category_by_id[id])
            .map((category) => {
                const isRootCategory = category.id === this.pos.db.root_category_id;
                const showSeparator =
                    !isRootCategory &&
                    [
                        ...this.pos.db.get_category_ancestors_ids(this.pos.selectedStockMoveCategoryId),
                        this.pos.selectedStockMoveCategoryId,
                    ].includes(category.id);
                return {
                    id: category.id,
                    name: !isRootCategory ? category.name : "",
                    type: !isRootCategory ? category.type : "default",
                    icon: isRootCategory ? "fa-home fa-2x" : "",
                    separator: "fa-caret-right",
                    showSeparator,
                    imageUrl:
                        category?.has_image &&
                        `/web/image?model=pos.category&field=image_128&id=${category.id}&unique=${category.write_date}`,
                };
            });
    }

    get selectedStockMoveCategoryId() {
        return this.pos.selectedStockMoveCategoryId;
    }
    get searchWord() {
        return this.pos.searchStockMoveProductWord.trim();
    }
    getProductListToNotDisplay() {
        return [this.pos.config.tip_product_id];
    }
    get productsToDisplay() {
        const { db } = this.pos;
        let list = [];
        if (this.searchWord !== "") {
            list = db.search_product_in_category(this.selectedStockMoveCategoryId, this.searchWord);
        } else {
            list = db.get_product_by_category(this.selectedStockMoveCategoryId);
        }
        const categoryIdList = this.getCheckStockMoveCategoryId();
        list = list.filter((product) => {
            return product.pos_categ_ids.some(id => categoryIdList.includes(id));
        });
        list = list.filter((product) => !this.getProductListToNotDisplay().includes(product.id));
        return list.sort(function (a, b) {
            return a.display_name.localeCompare(b.display_name);
        });
    }
    getCheckStockMoveCategoryId() {
        const categories = Object.values(this.pos.db.category_by_id);
        const category_id_list = [];
        categories.forEach((category) => {
            if (category.type == 'box') {
                category_id_list.push(category.id);
            }
        });
        // const hasCommonElement = category_id_list.some(item => pos_categ_ids.includes(item));
        return category_id_list;
    }
    get hasNoCategories() {
        return this.pos.db.get_category_childs_ids(0).length === 0;
    }
    get shouldShowButton() {
        return this.productsToDisplay.length === 0 && this.searchWord;
    }
    updateProductList(event) {
        this.pos.setSelectedStockMoveCategoryId(0);
    }
    async onPressEnterKey() {
        const { searchStockMoveProductWord } = this.pos;
        if (!searchStockMoveProductWord) {
            return;
        }
        if (this.state.previousSearchWord !== searchStockMoveProductWord) {
            this.state.currentOffset = 0;
        }
        const result = await this.loadProductFromDB();
        const cleanedProductWord = searchStockMoveProductWord.replace(/;product_tmpl_id:\d+$/, '');
        if (result.length > 0) {
            this.notification.add(
                _t('%s product(s) found for "%s".', result.length, cleanedProductWord),
                3000
            );
        } else {
            this.notification.add(_t('No more product found for "%s".', cleanedProductWord), 3000);
        }
        if (this.state.previousSearchWord === searchStockMoveProductWord) {
            this.state.currentOffset += result.length;
        } else {
            this.state.previousSearchWord = searchStockMoveProductWord;
            this.state.currentOffset = result.length;
        }
    }
    async loadProductFromDB() {
        const { searchStockMoveProductWord } = this.pos;
        if (!searchStockMoveProductWord) {
            return;
        }
        const cleanedProductWord = searchStockMoveProductWord.replace(/;product_tmpl_id:\d+$/, '');
        const domain = [
            "|",
            "|",
            ["name", "ilike", cleanedProductWord],
            ["default_code", "ilike", cleanedProductWord],
            ["barcode", "ilike", cleanedProductWord],
            ["available_in_pos", "=", true],
            ["sale_ok", "=", true],
        ];

        const { limit_categories, iface_available_categ_ids } = this.pos.config;
        if (limit_categories && iface_available_categ_ids.length > 0) {
            domain.push(["pos_categ_ids", "in", iface_available_categ_ids]);
        }

        try {
            const limit = 30;
            const ProductIds = await this.orm.call(
                "product.product",
                "search",
                [
                    [
                        "&",
                        ["available_in_pos", "=", true],
                        "|",
                        "|",
                        ["name", "ilike", searchStockMoveProductWord],
                        ["default_code", "ilike", searchStockMoveProductWord],
                        ["barcode", "ilike", searchStockMoveProductWord],
                    ],
                ],
                {
                    offset: this.state.currentOffset,
                    limit: limit,
                }
            );
            if (ProductIds.length) {
                await this.pos._addProducts(ProductIds, false);
            }
            this.updateProductList();
            return ProductIds;
        } catch (error) {
            if (error instanceof ConnectionLostError || error instanceof ConnectionAbortedError) {
                return this.popup.add(OfflineErrorPopup, {
                    title: _t("Network Error"),
                    body: _t(
                        "Product is not loaded. Tried loading the product from the server but there is a network error."
                    ),
                });
            } else {
                throw error;
            }
        }
    }
    async loadDemoDataProducts() {
        try {
            this.state.loadingDemo = true;
            const { models_data, successful } = await this.orm.call(
                "pos.session",
                "load_product_frontend",
                [this.pos.pos_session.id]
            );
            if (!successful) {
                this.popup.add(ErrorPopup, {
                    title: _t("Demo products are no longer available"),
                    body: _t(
                        "A valid product already exists for Point of Sale. Therefore, demonstration products cannot be loaded."
                    ),
                });
                // But the received models_data is still used to update the current session.
            }
            if (!models_data) {
                this._showLoadDemoDataMissingDataError("models_data");
                return;
            }
            for (const dataName of ["pos.category", "product.product", "pos.order"]) {
                if (!models_data[dataName]) {
                    this._showLoadDemoDataMissingDataError(dataName);
                    return;
                }
            }
            this.pos.updateModelsData(models_data);
        } finally {
            this.state.loadingDemo = false;
        }
    }
    _showLoadDemoDataMissingDataError(missingData) {
        console.error(
            "Missing '",
            missingData,
            "' in pos.session:load_product_frontend server answer."
        );
    }

    createNewProducts() {
        window.open("/web#action=point_of_sale.action_client_product_menu", "_self");
    }
    async onProductInfoClick(product) {
        const info = await this.pos.getProductInfo(product, 1);
        this.popup.add(ProductInfoPopup, { info: info, product: product });
    }
}
