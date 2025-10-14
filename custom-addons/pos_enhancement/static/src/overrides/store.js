/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";


patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(loadedData);
        // this.add_registered_order(loadedData['pos.registered.order'],loadedData['pos.registered.order.line']);
    },
    add_registered_order(orders,lines) {
        let new_orders=[]
        orders.forEach(order => {
            let order_lines=lines.filter(line => line.order_id[0]==order.id)
            let new_values={
                id:order.id,
                name:order.name,
                partner_id:order.partner_id[0],
                statement_ids:[],
                lines:order_lines.map(line => ([0,0,{
                    id : line.id,
                    product_id:line.product_id[0],
                    price_unit:line.price_unit,
                    qty:line.qty,
                    custom_attribute_value_ids:[],
                    pack_lot_ids:[]

                }])),
            }
            let new_order=this.createReactiveOrder(new_values)
            new_orders.push(new_order)
            
        });

    },
    async _save_to_server(orders, options) {
        if (!orders || !orders.length) {
            return Promise.resolve([]);
        }
        this.set_synch("connecting", orders.length);
        options = options || {};
        var order_ids_to_sync = orders.map((o) => o.id);

        for (const order of orders) {
            order.to_invoice = options.to_invoice || false;
        }
        // we try to send the order. silent prevents a spinner if it takes too long. (unless we are sending an invoice,
        // then we want to notify the user that we are waiting on something )
        const orm = options.to_invoice ? this.orm : this.orm.silent;
        // const register_orders=orders.filter(order => this.db.get_partner_by_id(order.partner_id)?.is_donee)
        const pos_orders=orders.filter(order => !this.db.get_partner_by_id(order.data.partner_id)?.is_donee)
        const register_orders=orders.filter(order => this.db.get_partner_by_id(order.data.partner_id)?.is_donee)
        console.log("register_orders",register_orders)
        console.log("pos_orders",pos_orders)

        try {
            // FIXME POSREF timeout
            // const timeout = typeof options.timeout === "number" ? options.timeout : 30000 * orders.length;
            let serverIds = []
            if (register_orders.length) {
                let register_orders_server_ids = await orm.call(
                    "pos.registered.order",
                    "create_from_ui",
                    [register_orders, options.draft || false],
                    {
                        context: this._getCreateOrderContext(orders, options),
                    }
                );
                serverIds.push(...register_orders_server_ids)
            }

            if (pos_orders.length) {
                let pos_orders_server_ids = await orm.call(
                    "pos.order",
                    "create_from_ui",
                    [orders, options.draft || false],
                    {
                        context: this._getCreateOrderContext(orders, options),
                    }
                );
                serverIds.push(...pos_orders_server_ids)

            }
            // serverIds.push(...register_orders_server_ids,...pos_orders_server_ids)
            

            for (const serverId of serverIds) {
                const order = this.env.services.pos.orders.find(
                    (order) => order.name === serverId.pos_reference
                );

                if (order) {

                    order.server_id = serverId.id;
                    order.set_barcode(serverId.barcode) 
                }
            }
            for (const order_id of order_ids_to_sync) {
                this.db.remove_order(order_id);
            }

            this.failed = false;
            this.set_synch("connected");
            return serverIds;
        } catch (error) {
            console.warn("Failed to send orders:", orders);
            if (error.code === 200) {
                // Business Logic Error, not a connection problem
                // Hide error if already shown before ...
                if ((!this.failed || options.show_error) && !options.to_invoice) {
                    this.failed = error;
                    this.set_synch("error");
                    throw error;
                }
            }
            this.set_synch("disconnected");
            throw error;
        }
    }

});
