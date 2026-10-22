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
        });

        this._charts = {};

        onWillStart(async () => {
            await this.fetch_shops();
            await this.refresh();
        });

        onMounted(async () => {
            await this.render_all_charts();
        });
    }

    // ---------------- loaders ----------------
    async fetch_shops() {
        this.state.shops = await this.orm.call('pos.order', 'get_shops', []);
    }

    async refresh() {
        await this.fetch_data();
        await this.render_all_charts();
    }

    async fetch_data() {
        const cfg = this.state.config_id ? parseInt(this.state.config_id, 10) : null;
        const df = this.state.date_from || null;
        const dt = this.state.date_to   || null;

        const result = await this.orm.call('pos.order', 'get_refund_details', [cfg, df, dt]);
        this.state.total_sale         = result['total_sale'];
        this.state.total_order_count  = result['total_order_count'];
        this.state.total_refund_count = result['total_refund_count'];
        this.state.total_session      = result['total_session'];
        this.state.today_refund_total = result['today_refund_total'];
        this.state.today_sale         = result['today_sale'];

        const data = await this.orm.call('pos.order', 'get_details', [cfg, df, dt]);
        this.state.payment_details = data['payment_details'];
        this.state.top_salesperson = data['salesperson'];
        this.state.selling_product = data['selling_product'];
    }

    // ---------------- filter handlers ----------------
    async onchange_filter(ev) {
        await this.refresh();
    }

    async clear_filter() {
        this.state.config_id = null;
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

    // ---------------- sales chart ----------------
    load_sales_chart(option) {
        const self = this;
        const ctx = $("#canvas_1");
        const cfg = this.state.config_id ? parseInt(this.state.config_id, 10) : null;
        const df = this.state.date_from || null;
        const dt = this.state.date_to   || null;

        return this.orm.call('pos.order', 'get_department', [option, cfg, df, dt])
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
                    title: { display: true, position: "top",
                             text: "SALE DETAILS", fontSize: 18, fontColor: "#111" },
                    legend: { display: true, position: "bottom",
                              labels: { fontColor: "#333", fontSize: 16 } },
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
    _filter_args() {
        return [
            this.state.config_id ? parseInt(this.state.config_id, 10) : null,
            this.state.date_from || null,
            this.state.date_to   || null,
        ];
    }

    render_top_customer_graph() {
        const self = this;
        const ctx = $(".top_customer");
        return this.orm.call('pos.order', 'get_the_top_customer', this._filter_args())
            .then(function (arrays) {
                const data = {
                    labels: arrays[1],
                    datasets: [{
                        label: "",
                        data: arrays[0],
                        backgroundColor: [
                            "rgb(148, 22, 227)", "rgba(54, 162, 235)",
                            "rgba(75, 192, 192)", "rgba(153, 102, 255)", "rgba(10,20,30)",
                        ],
                        borderColor: [
                            "rgba(255, 99, 132)", "rgba(54, 162, 235)",
                            "rgba(75, 192, 192)", "rgba(153, 102, 255)", "rgba(10,20,30)",
                        ],
                        borderWidth: 1,
                    }],
                };
                const options = {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: { x: { title: { display: true, text: "Top Customer",
                                           position: "top", fontSize: 24, color: "#111" } } },
                    legend: { display: true, position: "bottom",
                              labels: { fontColor: "#333", fontSize: 16 } },
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
                const values = arrays[0];
                // Truncate long product names
                const labels = arrays[1].map(l => l && l.length > 30 ? l.substring(0, 30) + '…' : (l || ''));

                // Split positives and negatives
                const positives = values.map(v => v >= 0 ? v : null);
                const negatives = values.map(v => v < 0 ? v : null);

                const data = {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Sales',
                            data: positives,
                            backgroundColor: 'rgba(67, 233, 123, 0.85)',
                            borderColor: 'rgba(67, 233, 123, 1)',
                            borderWidth: 1,
                        },
                        {
                            label: 'Refunds',
                            data: negatives,
                            backgroundColor: 'rgba(255, 106, 136, 0.85)',
                            borderColor: 'rgba(255, 106, 136, 1)',
                            borderWidth: 1,
                        },
                    ],
                };
                const options = {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    scales: {
                        x: {
                            beginAtZero: true, // Keeps the 0-line centered when negatives exist
                            ticks: {
                                callback: v => Number(v).toLocaleString('en-US'),
                            },
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
                const values = arrays[0];
                // Truncate long category names
                const labels = arrays[1].map(l => l && l.length > 30 ? l.substring(0, 30) + '…' : (l || ''));

                // Split positives and negatives
                const positives = values.map(v => v >= 0 ? v : null);
                const negatives = values.map(v => v < 0 ? v : null);

                const data = {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Sales',
                            data: positives,
                            backgroundColor: 'rgba(67, 233, 123, 0.85)',
                            borderColor: 'rgba(67, 233, 123, 1)',
                            borderWidth: 1,
                        },
                        {
                            label: 'Refunds',
                            data: negatives,
                            backgroundColor: 'rgba(255, 106, 136, 0.85)',
                            borderColor: 'rgba(255, 106, 136, 1)',
                            borderWidth: 1,
                        },
                    ],
                };
                const options = {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    scales: {
                        x: {
                            beginAtZero: true, // Keeps the 0-line centered when negatives exist
                            ticks: {
                                callback: v => Number(v).toLocaleString('en-US'),
                            },
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

    // ---------------- tile click actions (unchanged) ----------------
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