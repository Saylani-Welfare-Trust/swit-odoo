/** @odoo-module */

import { registry } from "@web/core/registry";
import { EventBus } from "@odoo/owl";

class FeeVoucherFetcher extends EventBus {
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
        console.log("fetch",this.ordersToShow)
        this.trigger("update");
    }

    async _fetch(limit, offset) {
        const recurring_orders = await this._getOrderIdsForCurrentPage(limit, offset);

        this.totalCount = recurring_orders.length;
        return recurring_orders;
    }
    async _getOrderIdsForCurrentPage(limit, offset) {

        // const domain = this.searchDomain || [['is_fee_voucher','=',true],['state', '=', 'draft']]
        const domain = this.searchDomain || [['state', '=', 'draft']]
        this.pos.set_synch("connecting");
        const fee_vouchers = await this.orm.searchRead(
            "fee.box",
            domain,
            [
                "name",
                "partner_id",
                "amount",
                "date",
                "state",
                "amount",
            ],
            { offset, limit }
        );
        // const fee_vouchers = await this.orm.searchRead(
        //     "sale.order",
        //     domain,
        //     [
        //         "name",
        //         "partner_id",
        //         "amount_total",
        //         "date_order",
        //         "state",
        //         "user_id",
        //         "amount_unpaid",
        //     ],
        //     { offset, limit }
        // );
        console.log("fee_vouchers",fee_vouchers,domain)

        this.pos.set_synch("connected");
        return fee_vouchers;
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
        // const partner_id=this.pos.get_order().get_partner()
        // if (partner_id) { 
        //     searchDomain.push(["partner_id", "=", partner_id.id])
        // }
        // searchDomain.push(('is_fee_voucher','=',true));
        this.searchDomain = searchDomain;
    }
    setNPerPage(val) {
        this.nPerPage = val;
    }
    setPage(page) {
        this.currentPage = page;
    }
}

export const FeeVoucherFetcherService = {
    dependencies: FeeVoucherFetcher.serviceDependencies,
    start(env, deps) {
        return new FeeVoucherFetcher(deps);
    },
};

registry.category("services").add("fee_voucher_fetcher_service", FeeVoucherFetcherService);
