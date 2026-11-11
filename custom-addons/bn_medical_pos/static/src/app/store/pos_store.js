/** @odoo-module */

import { reactive } from "@odoo/owl";
import { PosBus } from "@point_of_sale/app/bus/pos_bus_service";
import { PosDB } from "@point_of_sale/app/store/db";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { unaccent } from "@web/core/utils/strings";
import { _t } from "@web/core/l10n/translation";

// What the POS indexes per category: rebuilt when the Medical & Health categories change
const CATALOG_KEYS = [
    "category_by_id",
    "category_childs",
    "category_parent",
    "category_ancestors",
    "product_by_category_id",
    "category_search_string",
];

patch(PosStore.prototype, {
    async load_server_data() {
        await super.load_server_data(...arguments);
        if (this.config.is_medical_pos) {
            // remember what was loaded, to notice the changes made while the counter is open
            this.mhRefreshCatalog({ init: true });
        }
    },

    /** The products show only once a category is selected: a medical counter opens on one */
    resetProductScreenSearch() {
        super.resetProductScreenSearch(...arguments);
        if (this.config.is_medical_pos) {
            this.selectedCategoryId = this.mhDefaultCategoryId();
        }
    },

    add_new_order() {
        const order = super.add_new_order(...arguments);
        // in case a change wasn't received (e.g. connection lost meanwhile)
        if (this.config.is_medical_pos && this.mhCatalogStamp) {
            this.mhRefreshCatalog();
        }
        return order;
    },

    /** The counter's start category if it is loaded, else the first Medical & Health category */
    mhDefaultCategoryId({ keepCurrent = false } = {}) {
        const db = this.db;
        const isShown = (id) => id && id !== db.root_category_id && db.category_by_id[id];
        if (keepCurrent && isShown(this.selectedCategoryId)) {
            return this.selectedCategoryId;
        }
        const { start_category, iface_start_categ_id } = this.config;
        const startId = start_category && iface_start_categ_id?.[0];
        if (isShown(startId)) {
            return startId;
        }
        return db.get_category_childs_ids(db.root_category_id)[0] || db.root_category_id;
    },

    async mhRefreshCatalog({ init = false } = {}) {
        if (this.mhCatalogRefreshing) {
            this.mhCatalogRefreshPending = true;
            return;
        }
        this.mhCatalogRefreshing = true;
        try {
            const result = await this.orm.silent.call("pos.session", "mh_load_catalog", [
                [this.pos_session.id],
                this.mhCatalogStamp || false,
                init,
            ]);
            if (!init && result.changed) {
                await this.mhApplyCatalog(result);
                this.env.services.notification.add(_t("The product categories were updated."), {
                    type: "info",
                });
            }
            this.mhCatalogStamp = result.stamp;
        } catch (error) {
            // offline: the next order tries again
            console.warn("Medical & Health: categories not refreshed", error);
        } finally {
            this.mhCatalogRefreshing = false;
            if (this.mhCatalogRefreshPending) {
                this.mhCatalogRefreshPending = false;
                this.mhRefreshCatalog();
            }
        }
    },

    /** Replace the categories and the products shown per category, without reloading the POS */
    async mhApplyCatalog({ categories, products }) {
        const missingIds = products.map((p) => p.id).filter((id) => !this.db.get_product_by_id(id));
        if (missingIds.length) {
            await this._addProducts(missingIds, false);
        }

        const fresh = Object.create(PosDB.prototype);
        fresh.root_category_id = this.db.root_category_id;
        for (const key of CATALOG_KEYS) {
            fresh[key] = {};
        }
        fresh.add_categories(categories);
        for (const { id, pos_categ_ids } of products) {
            const product = this.db.get_product_by_id(id);
            if (!product) {
                continue;
            }
            product.pos_categ_ids = pos_categ_ids;
            const searchString = unaccent(this.db._product_search_string(product));
            const categoryIds = pos_categ_ids.length ? pos_categ_ids : [fresh.root_category_id];
            for (const categoryId of categoryIds) {
                for (const id2 of [categoryId, ...(fresh.get_category_ancestors_ids(categoryId) || [])]) {
                    (fresh.product_by_category_id[id2] ||= []).push(id);
                    fresh.category_search_string[id2] = (fresh.category_search_string[id2] || "") + searchString;
                }
            }
        }

        // through the reactive proxies, so the product screen renders again
        const db = reactive(this.db);
        for (const key of CATALOG_KEYS) {
            db[key] = fresh[key];
        }
        reactive(this).setSelectedCategoryId(this.mhDefaultCategoryId({ keepCurrent: true }));
    },
});

patch(PosBus.prototype, {
    dispatch(message) {
        super.dispatch(...arguments);
        if (message.type === "MH_CATALOG_CHANGED" && this.pos.config.is_medical_pos) {
            this.pos.mhRefreshCatalog();
        }
    },
});
