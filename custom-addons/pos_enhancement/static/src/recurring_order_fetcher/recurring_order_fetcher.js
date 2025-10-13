/** @odoo-module */

import { registry } from "@web/core/registry";
import { EventBus } from "@odoo/owl";

class RecurringOrderFetcher extends EventBus {
    static serviceDependencies = ["orm", "pos"];

    constructor({ orm, pos }) {
        super();
        this.currentPage = 1;
        this.ordersToShow = [];
        this.totalCount = 0;
        this.orm = orm;
        this.pos = pos;
        
    }


    get lastPage() {
        const nItems = this.totalCount;
        return Math.trunc(nItems / (this.nPerPage + 1)) + 1;
    }

    async fetch() {
        // Show orders from the backend.
        const offset = this.nPerPage + (this.currentPage - 1 - 1) * this.nPerPage;
        const limit = this.nPerPage;
        this.ordersToShow = await this._fetch(limit, offset);

        this.trigger("update");
    }

    async _fetch(limit, offset) {
        const recurring_orders = await this._getOrderIdsForCurrentPage(limit, offset);

        this.totalCount = recurring_orders.length;
        return recurring_orders;
    }
    async _getOrderIdsForCurrentPage(limit, offset) {

        const domain = this.searchDomain || []
        console.log("domain",domain)
        this.pos.set_synch("connecting");
        const recurring_orders = await this.orm.searchRead(
            "pos.registered.order",
            domain,
            [
                "name",
                "partner_id",
                "create_date",
                "state",
                "registrar",
                "disbursement_type",
                "transaction_type",
                "amount_total",
                "is_payment_validated"
            ],
            { offset, limit }
        );
        console.log(recurring_orders)
        this.pos.set_synch("connected");
        return recurring_orders;
    }

    nextPage() {
        if (this.currentPage < this.lastPage) {
            this.currentPage += 1;
            this.fetch();
        }
    }
    prevPage() {
        if (this.currentPage > 1) {
            this.currentPage -= 1;
            this.fetch();
        }
    }

    get(id) {
        return this.ordersToShow;
    }
    setSearchDomain(searchDomain) {
        const partner_id=this.pos.get_order().get_partner()
        if (partner_id) { 
            searchDomain.push(["partner_id", "=", partner_id.id])
        }
        this.searchDomain = searchDomain;
    }
    setNPerPage(val) {
        this.nPerPage = val;
    }
    setPage(page) {
        this.currentPage = page;
    }
}

export const RecurringOrderFetcherService = {
    dependencies: RecurringOrderFetcher.serviceDependencies,
    start(env, deps) {
        return new RecurringOrderFetcher(deps);
    },
};

registry.category("services").add("recurring_order_fetcher", RecurringOrderFetcherService);
