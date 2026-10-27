/** @odoo-module **/
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PosDashboard extends Component {
    setup() {
        super.setup(...arguments);
        this.orm = useService('orm');
        this.user = useService("user");
        this.actionService = useService("action");

        // FLAG to check if the DOM is fully loaded
        this.is_mounted = false;

        this.state = useState({
            // shop / location / segment
            config_id: null,
            shops: [],
            province_id: null,
            city_id: null,
            segment_id: null,
            provinces: [],
            cities: [],
            segments: [],
            // product category
            category_id: null,
            categories: [],
            // amount range
            amount_min: null,
            amount_max: null,
            // date
            date_from: '',
            date_to: '',
            sales_period: 'pos_hourly_sales',
            // data buckets
            payment_details: [],
            top_salesperson: [],
            selling_product: [],
            total_sale: [],
            total_order_count: [],
            total_refund_count: [],
            total_session: [],
            today_refund_total: [],
            today_sale: [],
            cheque_count: 0,
            deposit_count: 0,
            transfer_count: 0,
        });

        this._charts = {};

        onWillStart(async () => {
            await this.fetch_dropdowns();
            await this.fetch_data(); // Only fetch data here, do NOT render charts yet
        });

        onMounted(async () => {
            this.is_mounted = true; // DOM is now ready
            await this.render_all_charts();
        });
    }

    // ---------------- loaders ----------------
    async fetch_dropdowns() {
        this.state.shops = await this.orm.call('pos.order', 'get_shops', []);
        const hierarchy = await this.orm.call('pos.order', 'get_location_hierarchy', []);
        this.state.provinces = hierarchy.provinces || [];
        this.state.cities = hierarchy.cities || [];
        this.state.segments = hierarchy.segments || [];

        // Load product categories
        this.state.categories = await this.orm.searchRead(
            'product.category',
            [],
            ['id', 'name'],
            { order: 'complete_name asc', limit: 1000 }
        );
    }

    get filteredCities() {
        if (!this.state.province_id) return this.state.cities;
        const pId = parseInt(this.state.province_id, 10);
        return this.state.cities.filter(c => c.province_id === pId);
    }

    async refresh() {
        await this.fetch_data();
        if (this.is_mounted) {
            await this.render_all_charts();
        }
    }

    async fetch_data() {
        const args = this._filter_args();
        const result = await this.orm.call('pos.order', 'get_refund_details', args);

        this.state.total_sale         = result['total_sale'];
        this.state.total_order_count  = (result['total_order_count'] || 0).toLocaleString('en-US');
        this.state.total_refund_count = (result['total_refund_count'] || 0).toLocaleString('en-US');
        this.state.total_session      = (result['total_session'] || 0).toLocaleString('en-US');
        this.state.today_refund_total = (result['today_refund_total'] || 0).toLocaleString('en-US');
        this.state.today_sale         = (result['today_sale'] || 0).toLocaleString('en-US');

        const data = await this.orm.call('pos.order', 'get_details', args);
        this.state.payment_details = data['payment_details'];
        this.state.top_salesperson = data['salesperson'];
        this.state.selling_product = data['selling_product'];

        this.state.top_products_amount = await this.orm.call('pos.order', 'get_top_products_by_amount', args);

        const treasury = await this.orm.call('pos.order', 'get_treasury_stats', args);
        this.state.cheque_count   = (treasury.cheque_count   || 0).toLocaleString('en-US');
        this.state.deposit_count  = (treasury.deposit_count  || 0).toLocaleString('en-US');
        this.state.transfer_count = (treasury.transfer_count || 0).toLocaleString('en-US');
    }

    // ---------------- filter handlers ----------------
    async onchange_province() {
        this.state.city_id = null;
        await this.refresh();
    }

    async onchange_filter() {
        await this.refresh();
    }

    async clear_filter() {
        this.state.config_id   = null;
        this.state.province_id = null;
        this.state.city_id     = null;
        this.state.segment_id  = null;
        this.state.category_id = null;
        this.state.amount_min  = null;
        this.state.amount_max  = null;
        this.state.date_from   = '';
        this.state.date_to     = '';
        await this.refresh();
    }

    async set_quick_date(type) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const month = today.getMonth();

        if (type === 'this_month') {
            this.state.date_from = this._fmt_date(new Date(yyyy, month, 1));
            this.state.date_to   = this._fmt_date(new Date(yyyy, month + 1, 0));
        } else if (type === 'last_month') {
            this.state.date_from = this._fmt_date(new Date(yyyy, month - 1, 1));
            this.state.date_to   = this._fmt_date(new Date(yyyy, month, 0));
        } else if (type === 'this_year') {
            this.state.date_from = `${yyyy}-01-01`;
            this.state.date_to   = `${yyyy}-12-31`;
        } else if (type === 'today') {
            const d = this._fmt_date(today);
            this.state.date_from = d;
            this.state.date_to   = d;
        }
        await this.refresh();
    }

    _fmt_date(d) {
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    }

    _filter_args() {
        const num = (v) => (v === null || v === undefined || v === '') ? null : parseFloat(v);
        return [
            this.state.config_id   ? parseInt(this.state.config_id, 10)   : null,
            this.state.date_from   || null,
            this.state.date_to     || null,
            this.state.province_id ? parseInt(this.state.province_id, 10) : null,
            this.state.city_id     ? parseInt(this.state.city_id, 10)     : null,
            this.state.segment_id  ? parseInt(this.state.segment_id, 10)  : null,
            this.state.category_id ? parseInt(this.state.category_id, 10) : null,
            num(this.state.amount_min),
            num(this.state.amount_max),
        ];
    }

    // ---------------- charts ----------------
    load_sales_chart(option) {
        const self = this;
        const ctx = $("#canvas_1");
        if (!ctx.length) return; // Safety check

        const args = this._filter_args();

        return this.orm.call('pos.order', 'get_department', [option, ...args])
            .then(function (arrays) {
                const data = {
                    labels: arrays[1],
                    datasets: [{
                        label: arrays[2],
                        data: arrays[0],
                        backgroundColor: [
                            "rgba(255, 99, 132,1)", "rgba(54, 162, 235,1)",
                            "rgba(75, 192, 192,1)", "rgba(153, 102, 255,1)",
                            "rgba(10,20,30,1)",
                        ],
                        borderWidth: 1,
                    }],
                };
                const options = {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: true, position: "bottom" } },
                };
                if (self._charts.sales_chart) self._charts.sales_chart.destroy();
                self._charts.sales_chart = new Chart(ctx, { type: "bar", data, options });
            });
    }

    onclick_pos_sales(ev) {
        const option = $(ev.target).val();
        if (!option) return;
        this.state.sales_period = option;
        this.load_sales_chart(option);
    }

    async render_all_charts() {
        await this.render_top_customer_graph();
        await this.render_top_product_graph();
        await this.render_product_category_graph();
        await this.load_sales_chart(this.state.sales_period || 'pos_hourly_sales');
    }

    render_top_customer_graph() {
        const self = this;
        const ctx = $(".top_customer");
        if (!ctx.length) return;

        return this.orm.call('pos.order', 'get_the_top_customer', this._filter_args())
            .then(function (arrays) {
                const data = {
                    labels: arrays[1].map(l => l && l.length > 22 ? l.substring(0, 22) + '…' : (l || '')),
                    datasets: [{
                        data: arrays[0],
                        backgroundColor: [
                            "rgb(148, 22, 227)", "rgba(54, 162, 235)",
                            "rgba(75, 192, 192)", "rgba(153, 102, 255)",
                            "rgba(10,20,30)",   "rgba(255, 99, 132)",
                        ],
                        borderColor: "#fff", borderWidth: 2,
                    }],
                };
                const options = {
                    responsive: true, maintainAspectRatio: false,
                    legend: { display: true, position: 'right', labels: { font: { size: 10 }, padding: 6 } },
                    tooltip: { callbacks: { label: function (ctx) { return (arrays[1][ctx.dataIndex] || '') + ': ' + ctx.parsed.toLocaleString('en-US'); } } },
                };
                if (self._charts.top_customer) self._charts.top_customer.destroy();
                self._charts.top_customer = new Chart(ctx, { type: "pie", data, options });
            });
    }

    render_top_product_graph() {
        const self = this;
        const ctx = $(".top_selling_product");
        if (!ctx.length) return;

        return this.orm.call('pos.order', 'get_the_top_products', this._filter_args())
            .then(function (arrays) {
                const data = {
                    labels: arrays[2].map(l => l && l.length > 30 ? l.substring(0, 30) + '…' : (l || '')),
                    datasets: [
                        { label: 'Sales', data: arrays[0], backgroundColor: 'rgba(67, 233, 123, 0.85)', minBarLength: 4 },
                        { label: 'Refunds', data: arrays[1], backgroundColor: 'rgba(255, 106, 136, 0.85)', minBarLength: 4 },
                    ],
                };
                const options = {
                    responsive: true, maintainAspectRatio: false, indexAxis: 'y',
                    scales: { x: { stacked: false, ticks: { callback: v => Number(v).toLocaleString('en-US') } } },
                    plugins: { legend: { position: "bottom" } },
                };
                if (self._charts.top_products) self._charts.top_products.destroy();
                self._charts.top_products = new Chart(ctx, { type: "bar", data, options });
            });
    }

    render_product_category_graph() {
        const self = this;
        const ctx = $(".top_product_categories");
        if (!ctx.length) return;

        return this.orm.call('pos.order', 'get_the_top_categories', this._filter_args())
            .then(function (arrays) {
                const data = {
                    labels: arrays[2].map(l => l && l.length > 30 ? l.substring(0, 30) + '…' : (l || '')),
                    datasets: [
                        { label: 'Sales', data: arrays[0], backgroundColor: 'rgba(67, 233, 123, 0.85)', minBarLength: 4 },
                        { label: 'Refunds', data: arrays[1], backgroundColor: 'rgba(255, 106, 136, 0.85)', minBarLength: 4 },
                    ],
                };
                const options = {
                    responsive: true, maintainAspectRatio: false, indexAxis: 'y',
                    scales: { x: { stacked: false, ticks: { callback: v => Number(v).toLocaleString('en-US') } } },
                    plugins: { legend: { position: "bottom" } },
                };
                if (self._charts.top_categories) self._charts.top_categories.destroy();
                self._charts.top_categories = new Chart(ctx, { type: "bar", data, options });
            });
    }

    // ---------------- view all actions ----------------
    open_view_all(type) {
        let res_model = type === 'products' ? 'product.template' : 'product.category';
        let name = type === 'products' ? 'All Products' : 'All Product Categories';
        this.actionService.doAction({
            name: name, type: 'ir.actions.act_window', res_model: res_model,
            views: [[false, 'list'], [false, 'form']], target: 'current',
        });
    }

    open_treasury_orders(ttype) {
        const args = this._filter_args();
        this.orm.call('pos.order', 'action_get_treasury_orders', [ttype, ...args])
            .then(action => { this.actionService.doAction(action); });
    }

    // ---------------- tile click actions ----------------
    pos_order_today(e) {
        const date = new Date();
        const yesterday = new Date(date.getTime());
        yesterday.setDate(date.getDate() - 1);
        e.stopPropagation(); e.preventDefault();
        this.actionService.doAction({
            name: _t("Today Order"), type: 'ir.actions.act_window', res_model: 'pos.order',
            views: [[false, 'list'], [false, 'form']],
            domain: [['date_order', '<=', date], ['date_order', '>=', yesterday]], target: 'current',
        });
    }

    pos_refund_orders(e) {
        e.stopPropagation(); e.preventDefault();
        this.actionService.doAction({
            name: _t("Refund Orders"), type: 'ir.actions.act_window', res_model: 'pos.order',
            views: [[false, 'list'], [false, 'form']],
            domain: [['amount_total', '<', 0.0]], target: 'current',
        });
    }

    pos_refund_today_orders(e) {
        const date = new Date();
        const yesterday = new Date(date.getTime());
        yesterday.setDate(date.getDate() - 1);
        e.stopPropagation(); e.preventDefault();
        this.actionService.doAction({
            name: _t("Refund Orders"), type: 'ir.actions.act_window', res_model: 'pos.order',
            views: [[false, 'list'], [false, 'form']],
            domain: [['amount_total', '<', 0.0], ['date_order', '<=', date], ['date_order', '>=', yesterday]], target: 'current',
        });
    }

    pos_order(e) {
        e.stopPropagation(); e.preventDefault();
        this.actionService.doAction({
            name: _t("Total Order"), type: 'ir.actions.act_window', res_model: 'pos.order',
            views: [[false, 'list'], [false, 'form']], target: 'current',
        });
    }

    pos_session(e) {
        e.stopPropagation(); e.preventDefault();
        this.actionService.doAction({
            name: _t("sessions"), type: 'ir.actions.act_window', res_model: 'pos.session',
            views: [[false, 'list'], [false, 'form']], target: 'current',
        });
    }
}

PosDashboard.template = 'PosDashboard';
registry.category("actions").add("pos_order_menu", PosDashboard);