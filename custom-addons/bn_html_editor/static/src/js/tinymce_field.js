/** @odoo-module **/

import { Component, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class WordEditor extends Component {
    static template = "odoo_word_editor.WordEditor";
    static props = standardFieldProps;

    setup() {
        this.editorRef = useRef("editor");
        this.editor = null;

        onMounted(() => this.init());
        onWillUnmount(() => this.destroy());
    }

    init() {
        const value = this.props.record.data[this.props.name] || "";

        tinymce.init({
            target: this.editorRef.el,

            height: 800,
            menubar: true,

            plugins: [
                "lists link image table code fullscreen preview wordcount pagebreak"
            ],

            toolbar:
                "undo redo | styles | bold italic underline | " +
                "alignleft aligncenter alignright alignjustify | " +
                "bullist numlist | table | image link | " +
                "pagebreak | code fullscreen",

            content_style: `
                body {
                    font-family: Calibri, Arial, sans-serif;
                    font-size: 14px;
                    background: #f1f1f1;
                }

                .mce-content-body {
                    background: white;
                    width: 210mm;
                    min-height: 297mm;
                    margin: 20px auto;
                    padding: 20mm;
                    box-shadow: 0 0 10px rgba(0,0,0,0.2);
                }
            `,

            setup: (editor) => {
                this.editor = editor;

                editor.on("init", () => {
                    editor.setContent(value);
                });

                editor.on("change keyup undo redo", () => {
                    this.props.record.update({
                        [this.props.name]: editor.getContent(),
                    });
                });
            },
        });
    }

    destroy() {
        if (this.editor) {
            this.editor.remove();
        }
    }
}



registry.category("fields").add("word_editor", {
    component: WordEditor,
});