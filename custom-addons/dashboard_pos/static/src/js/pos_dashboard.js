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

        this.state = useState({
            config_id: null,
            shops: [],
            province_id: null,
            city_id: null,
            segment_id: null,
            product_type: null,
            provinces: [],
            cities: [],
            segments: [],
            product_types: [
                { value: 'is_course', name: 'Is Course' },
                { value: 'is_medical_equipment', name: 'Is Medical Equipment' },
                { value: 'is_livestock', name: 'Is Livestock' },
                { value: 'is_donation_box', name: 'Is Donation Box' },
                { value: 'is_microfinance', name: 'Is Microfinance' },
                { value: 'is_advance_donation', name: 'Is Advance Donation' },
                { value: 'is_service_charge', name: 'Is Service Charge' },
                { value: 'is_qurbani_inventory', name: 'Is Qurbani Inventory' },
                { value: 'is_pos_qurbani_inventory', name: 'Is POS Qurbani Inv.' },
                { value: 'is_donation_in_kind', name: 'Is Donation In Kind' },
                { value: 'is_livestock_product', name: 'Is Livestock Product' },
                { value: 'is_kitchen', name: 'Is Kitchen' },
            ],
            date_from: '',
            date_to: '',
            sales_period: 'pos_hourly_sales',
            payment_details: [],
            top_salesperson: [],
            selling_product: [],
            total_sale: [],
            total_order_count: [],
            total_refund_count: [],
            total_session: [],
            today_refund_total: [],
            today_sale: [],
            // NEW TREASURY COUNTS
            cheque_count: 0,
            deposit_count: 0,
            transfer_count: 0,
        });

        this._charts = {};

        onWillStart(async () => {
            await this.fetch_dropdowns();
            await this.refresh();
        });

        onMounted(async () => {
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
    }

    get filteredCities() {
        if (!this.state.province_id) return this.state.cities;
        const pId = parseInt(this.state.province_id, 10);
        return this.state.cities.filter(c => c.province_id === pId);
    }

    async refresh() {
        await this.fetch_data();
        await this.render_all_charts();
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

        // Fetch Treasury Counts
        const treasury = await this.orm.call('pos.order', 'get_treasury_stats', args);
        this.state.cheque_count = (treasury.cheque_count || 0).toLocaleString('en-US');
        this.state.deposit_count = (treasury.deposit_count || 0).toLocaleString('en-US');
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
        this.state.config_id = null;
        this.state.province_id = null;
        this.state.city_id = null;
        this.state.segment_id = null;
        this.state.product_type = null;
        this.state.date_from = '';
        this.state.date_to   = '';
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
        return [
            this.state.config_id ? parseInt(this.state.config_id, 10) : null,
            this.state.date_from || null,
            this.state.date_to   || null,
            this.state.province_id ? parseInt(this.state.province_id, 10) : null,
            this.state.city_id ? parseInt(this.state.city_id, 10) : null,
            this.state.segment_id ? parseInt(this.state.segment_id, 10) : null,
            this.state.product_type || null,
        ];
    }

    // ---------------- sales chart ----------------
    load_sales_chart(option) {
        const self = this;
        const ctx = $("#canvas_1");
        const args = this._filter_args();

        return this.orm.call('pos.order', 'get_department', [option, ...args])
            .then(function (arrays) {
                const data = {
                    labels: arrays[1],
                    datasets: [{
                        label: arrays[2],
                        data: arrays[0],
                        backgroundColor: [
                            "rgba(255, 99, 132,1)",
                            "rgba(54, 162, 235,1)",
                            "rgba(75, 192, 192,1)",
                            "rgba(153, 102, 255,1)",
                            "rgba(10,20,30,1)",
                        ],
                        borderColor: [
                            "rgba(255, 99, 132, 0.2)",
                            "rgba(54, 162, 235, 0.2)",
                            "rgba(75, 192, 192, 0.2)",
                            "rgba(153, 102, 255, 0.2)",
                            "rgba(10,20,30,0.3)",
                        ],
                        borderWidth: 1,
                    }],
                };
                const options = {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: true, position: "bottom",
                                  labels: { fontColor: "#333", fontSize: 16 } },
                    },
                };
                if (window.myCharts != undefined) window.myCharts.destroy();
                window.myCharts = new Chart(ctx, { type: "bar", data, options });
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

    // ---------------- pie / bar charts ----------------
    render_top_customer_graph() {
        const self = this;
        const ctx = $(".top_customer");
        return this.orm.call('pos.order', 'get_the_top_customer', this._filter_args())
            .then(function (arrays) {
                const labels = arrays[1].map(l => l && l.length > 22 ? l.substring(0, 22) + '…' : (l || ''));

                const data = {
                    labels: labels,
                    datasets: [{
                        data: arrays[0],
                        backgroundColor: [
                            "rgb(148, 22, 227)", "rgba(54, 162, 235)",
                            "rgba(75, 192, 192)", "rgba(153, 102, 255)",
                            "rgba(10,20,30)",   "rgba(255, 99, 132)",
                            "rgba(120, 200, 90)", "rgba(255, 159, 64)",
                            "rgba(201, 203, 207)", "rgba(100, 100, 100)",
                        ],
                        borderColor: "#fff",
                        borderWidth: 2,
                    }],
                };

                const options = {
                    responsive: true,
                    maintainAspectRatio: false,
                    legend: {
                        display: true,
                        position: 'right',
                        labels: { font: { size: 10 }, boxWidth: 10, boxHeight: 10, padding: 6 },
                    },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                const full = arrays[1][ctx.dataIndex] || '';
                                return full + ': ' + ctx.parsed.toLocaleString('en-US');
                            },
                        },
                    },
                };

                if (self._charts.top_customer) self._charts.top_customer.destroy();
                self._charts.top_customer = new Chart(ctx, { type: "pie", data, options });
            });
    }

    render_top_product_graph() {
        const self = this;
        const ctx = $(".top_selling_product");
        return this.orm.call('pos.order', 'get_the_top_products', this._filter_args())
            .then(function (arrays) {
                const sales = arrays[0];
                const refunds = arrays[1];
                const labels = arrays[2].map(l => l && l.length > 30 ? l.substring(0, 30) + '…' : (l || ''));

                const data = {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Sales',
                            data: sales,
                            backgroundColor: 'rgba(67, 233, 123, 0.85)',
                            borderColor: 'rgba(67, 233, 123, 1)',
                            borderWidth: 1,
                            minBarLength: 4, 
                        },
                        {
                            label: 'Refunds',
                            data: refunds,
                            backgroundColor: 'rgba(255, 106, 136, 0.85)',
                            borderColor: 'rgba(255, 106, 136, 1)',
                            borderWidth: 1,
                            minBarLength: 4, 
                        },
                    ],
                };
                const options = {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    scales: {
                        x: {
                            stacked: false,
                            ticks: { callback: v => Number(v).toLocaleString('en-US') },
                        },
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: "bottom",
                            labels: { font: { size: 12 }, boxWidth: 12, padding: 10 },
                        },
                    },
                };
                if (self._charts.top_products) self._charts.top_products.destroy();
                self._charts.top_products = new Chart(ctx, { type: "bar", data, options });
            });
    }

    render_product_category_graph() {
        const self = this;
        const ctx = $(".top_product_categories");
        return this.orm.call('pos.order', 'get_the_top_categories', this._filter_args())
            .then(function (arrays) {
                const sales = arrays[0];
                const refunds = arrays[1];
                const labels = arrays[2].map(l => l && l.length > 30 ? l.substring(0, 30) + '…' : (l || ''));

                const data = {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Sales',
                            data: sales,
                            backgroundColor: 'rgba(67, 233, 123, 0.85)',
                            borderColor: 'rgba(67, 233, 123, 1)',
                            borderWidth: 1,
                            minBarLength: 4, 
                        },
                        {
                            label: 'Refunds',
                            data: refunds,
                            backgroundColor: 'rgba(255, 106, 136, 0.85)',
                            borderColor: 'rgba(255, 106, 136, 1)',
                            borderWidth: 1,
                            minBarLength: 4, 
                        },
                    ],
                };
                const options = {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    scales: {
                        x: {
                            stacked: false,
                            ticks: { callback: v => Number(v).toLocaleString('en-US') },
                        },
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: "bottom",
                            labels: { font: { size: 12 }, boxWidth: 12, padding: 10 },
                        },
                    },
                };
                if (self._charts.top_categories) self._charts.top_categories.destroy();
                self._charts.top_categories = new Chart(ctx, { type: "bar", data, options });
            });
    }

    // ---------------- view all actions ----------------
    open_view_all(type) {
        let res_model = '';
        let name = '';
        let context = {};

        if (type === 'products') {
            res_model = 'product.template';
            name = 'All Products';
        } else if (type === 'categories') {
            res_model = 'product.category';
            name = 'All Product Categories';
        }

        this.actionService.doAction({
            name: name,
            type: 'ir.actions.act_window',
            res_model: res_model,
            views: [[false, 'list'], [false, 'form']],
            target: 'current',
            context: context,
        });
    }

    // ---------------- treasury integration ----------------
    open_treasury_orders(ttype) {
        const args = this._filter_args();
        this.orm.call('pos.order', 'action_get_treasury_orders', [ttype, ...args])
            .then(action => {
                this.actionService.doAction(action);
            });
    }

    // ---------------- tile click actions ----------------
    pos_order_today(e) {
        const self = this;
        const date = new Date();
        const yesterday = new Date(date.getTime());
        yesterday.setDate(date.getDate() - 1);
        e.stopPropagation(); e.preventDefault();
        this.user.hasGroup('hr.group_hr_user').then(function (has_group) {
            if (!has_group) return;
            self.actionService.doAction({
                name: _t("Today Order"),
                type: 'ir.actions.act_window',
                res_model: 'pos.order',
                view_mode: 'tree,form,calendar',
                views: [[false, 'list'], [false, 'form']],
                domain: [['date_order', '<=', date], ['date_order', '>=', yesterday]],
                target: 'current',
            }, { on_reverse_breadcrumb: self.on_reverse_breadcrumb });
        });
    }

    pos_refund_orders(e) {
        const self = this;
        e.stopPropagation(); e.preventDefault();
        this.user.hasGroup('hr.group_hr_user').then(function (has_group) {
            if (!has_group) return;
            self.actionService.doAction({
                name: _t("Refund Orders"),
                type: 'ir.actions.act_window',
                res_model: 'pos.order',
                view_mode: 'tree,form,calendar',
                views: [[false, 'list'], [false, 'form']],
                domain: [['amount_total', '<', 0.0]],
                target: 'current',
            }, { on_reverse_breadcrumb: self.on_reverse_breadcrumb });
        });
    }

    pos_refund_today_orders(e) {
        const self = this;
        const date = new Date();
        const yesterday = new Date(date.getTime());
        yesterday.setDate(date.getDate() - 1);
        e.stopPropagation(); e.preventDefault();
        this.user.hasGroup('hr.group_hr_user').then(function (has_group) {
            if (!has_group) return;
            self.actionService.doAction({
                name: _t("Refund Orders"),
                type: 'ir.actions.act_window',
                res_model: 'pos.order',
                view_mode: 'tree,form,calendar',
                views: [[false, 'list'], [false, 'form']],
                domain: [['amount_total', '<', 0.0],
                         ['date_order', '<=', date], ['date_order', '>=', yesterday]],
                target: 'current',
            }, { on_reverse_breadcrumb: self.on_reverse_breadcrumb });
        });
    }

    pos_order(e) {
        const self = this;
        e.stopPropagation(); e.preventDefault();
        this.user.hasGroup('hr.group_hr_user').then(function (has_group) {
            if (!has_group) return;
            self.actionService.doAction({
                name: _t("Total Order"),
                type: 'ir.actions.act_window',
                res_model: 'pos.order',
                view_mode: 'tree,form,calendar',
                views: [[false, 'list'], [false, 'form']],
                target: 'current',
            }, { on_reverse_breadcrumb: self.on_reverse_breadcrumb });
        });
    }

    pos_session(e) {
        const self = this;
        e.stopPropagation(); e.preventDefault();
        this.user.hasGroup('hr.group_hr_user').then(function (has_group) {
            if (!has_group) return;
            self.actionService.doAction({
                name: _t("sessions"),
                type: 'ir.actions.act_window',
                res_model: 'pos.session',
                view_mode: 'tree,form,calendar',
                views: [[false, 'list'], [false, 'form']],
                target: 'current',
            }, { on_reverse_breadcrumb: self.on_reverse_breadcrumb });
        });
    }
}

PosDashboard.template = 'PosDashboard';
registry.category("actions").add("pos_order_menu", PosDashboard);