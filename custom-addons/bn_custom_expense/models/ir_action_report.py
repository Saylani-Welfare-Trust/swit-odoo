import io
from odoo import models
from odoo.tools.pdf import PdfFileWriter, PdfFileReader
from odoo.exceptions import UserError

from PIL import Image

from collections import OrderedDict


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        # OVERRIDE
        report = self._get_report(report_ref)
        if report.report_name == 'hr_expense.report_expense_sheet':
            # expense_sheets = self.env['hr.expense.sheet'].browse(res_ids)
            # for expense_sheet in expense_sheets:
            #     # Will contains the expense report
            #     stream_list = []
            #     stream = res[expense_sheet.id]['stream']
            #     stream_list.append(stream)
            #     attachments = self.env['ir.attachment'].search([('res_id', 'in', expense_sheet.expense_line_ids.ids), ('res_model', '=', 'hr.expense')])
            #     expense_report = OdooPdfFileReader(stream, strict=False)
            #     output_pdf = OdooPdfFileWriter()
            #     output_pdf.appendPagesFromReader(expense_report)
            #     for attachment in attachments:
            #         if attachment.mimetype == 'application/pdf':
            #             attachment_stream = pdf.to_pdf_stream(attachment)
            #         else:
            #             # In case the attachment is not a pdf we will create a new PDF from the template "report_expense_sheet_img"
            #             # And then append to the stream. By doing so, the attachment is put on a new page with the name of the expense
            #             # associated to the attachment
            #             data['attachment'] = attachment
            #             attachment_prep_stream = self._render_qweb_pdf_prepare_streams('hr_expense.report_expense_sheet_img', data, res_ids=res_ids)
            #             attachment_stream = attachment_prep_stream[expense_sheet.id]['stream']
            #         attachment_reader = OdooPdfFileReader(attachment_stream, strict=False)
            #         output_pdf.appendPagesFromReader(attachment_reader)
            #         stream_list.append(attachment_stream)

            #     new_pdf_stream = io.BytesIO()
            #     output_pdf.write(new_pdf_stream)
            #     res[expense_sheet.id]['stream'] = new_pdf_stream

            #     for stream in stream_list:
            #         stream.close()
            
            if not data:
                data = {}
            data.setdefault('report_type', 'pdf')

            # access the report details with sudo() but evaluation context as current user
            report_sudo = self._get_report(report_ref)
            has_duplicated_ids = res_ids and len(res_ids) != len(set(res_ids))

            collected_streams = OrderedDict()

            # Fetch the existing attachments from the database for later use.
            # Reload the stream from the attachment in case of 'attachment_use'.
            if res_ids:
                records = self.env[report_sudo.model].browse(res_ids)
                for record in records:
                    res_id = record.id
                    if res_id in collected_streams:
                        continue

                    stream = None
                    attachment = None
                    if not has_duplicated_ids and report_sudo.attachment and not self._context.get("report_pdf_no_attachment"):
                        attachment = report_sudo.retrieve_attachment(record)

                        # Extract the stream from the attachment.
                        if attachment and report_sudo.attachment_use:
                            stream = io.BytesIO(attachment.raw)

                            # Ensure the stream can be saved in Image.
                            if attachment.mimetype.startswith('image'):
                                img = Image.open(stream)
                                new_stream = io.BytesIO()
                                img.convert("RGB").save(new_stream, format="pdf")
                                stream.close()
                                stream = new_stream

                    collected_streams[res_id] = {
                        'stream': stream,
                        'attachment': attachment,
                    }

            # Call 'wkhtmltopdf' to generate the missing streams.
            res_ids_wo_stream = [res_id for res_id, stream_data in collected_streams.items() if not stream_data['stream']]
            all_res_ids_wo_stream = res_ids if has_duplicated_ids else res_ids_wo_stream
            is_whtmltopdf_needed = not res_ids or res_ids_wo_stream

            if is_whtmltopdf_needed:

                if self.get_wkhtmltopdf_state() == 'install':
                    # wkhtmltopdf is not installed
                    # the call should be catched before (cf /report/check_wkhtmltopdf) but
                    # if get_pdf is called manually (email template), the check could be
                    # bypassed
                    raise UserError(_("Unable to find Wkhtmltopdf on this system. The PDF can not be created."))

                # Disable the debug mode in the PDF rendering in order to not split the assets bundle
                # into separated files to load. This is done because of an issue in wkhtmltopdf
                # failing to load the CSS/Javascript resources in time.
                # Without this, the header/footer of the reports randomly disappear
                # because the resources files are not loaded in time.
                # https://github.com/wkhtmltopdf/wkhtmltopdf/issues/2083
                additional_context = {'debug': False}

                html = self.with_context(**additional_context)._render_qweb_html(report_ref, all_res_ids_wo_stream, data=data)[0]

                bodies, html_ids, header, footer, specific_paperformat_args = self.with_context(**additional_context)._prepare_html(html, report_model=report_sudo.model)

                if not has_duplicated_ids and report_sudo.attachment and set(res_ids_wo_stream) != set(html_ids):
                    raise UserError(_(
                        "The report's template %r is wrong, please contact your administrator. \n\n"
                        "Can not separate file to save as attachment because the report's template does not contains the"
                        " attributes 'data-oe-model' and 'data-oe-id' on the div with 'article' classname.",
                        report_sudo.name,
                    ))

                pdf_content = self._run_wkhtmltopdf(
                    bodies,
                    report_ref=report_ref,
                    header=header,
                    footer=footer,
                    landscape=self._context.get('landscape'),
                    specific_paperformat_args=specific_paperformat_args,
                    set_viewport_size=self._context.get('set_viewport_size'),
                )
                pdf_content_stream = io.BytesIO(pdf_content)

                # Printing a PDF report without any records. The content could be returned directly.
                if has_duplicated_ids or not res_ids:
                    return {
                        False: {
                            'stream': pdf_content_stream,
                            'attachment': None,
                        }
                    }

                # Split the pdf for each record using the PDF outlines.

                # Only one record: append the whole PDF.
                if len(res_ids_wo_stream) == 1:
                    collected_streams[res_ids_wo_stream[0]]['stream'] = pdf_content_stream
                    return collected_streams

                # In case of multiple docs, we need to split the pdf according the records.
                # In the simplest case of 1 res_id == 1 page, we use the PDFReader to print the
                # pages one by one.
                html_ids_wo_none = [x for x in html_ids if x]
                reader = PdfFileReader(pdf_content_stream)
                if reader.numPages == len(res_ids_wo_stream):
                    for i in range(reader.numPages):
                        attachment_writer = PdfFileWriter()
                        attachment_writer.addPage(reader.getPage(i))
                        stream = io.BytesIO()
                        attachment_writer.write(stream)
                        collected_streams[res_ids_wo_stream[i]]['stream'] = stream
                    return collected_streams

                # In cases where the number of res_ids != the number of pages,
                # we split the pdf based on top outlines computed by wkhtmltopdf.
                # An outline is a <h?> html tag found on the document. To retrieve this table,
                # we look on the pdf structure using pypdf to compute the outlines_pages from
                # the top level heading in /Outlines.
                if len(res_ids_wo_stream) > 1 and set(res_ids_wo_stream) == set(html_ids_wo_none):
                    root = reader.trailer['/Root']
                    has_valid_outlines = '/Outlines' in root and '/First' in root['/Outlines']
                    if not has_valid_outlines:
                        return {False: {
                            'report_action': self,
                            'stream': pdf_content_stream,
                            'attachment': None,
                        }}

                    outlines_pages = []
                    node = root['/Outlines']['/First']
                    while True:
                        outlines_pages.append(root['/Dests'][node['/Dest']][0])
                        if '/Next' not in node:
                            break
                        node = node['/Next']
                    outlines_pages = sorted(set(outlines_pages))

                    # The number of outlines must be equal to the number of records to be able to split the document.
                    has_same_number_of_outlines = len(outlines_pages) == len(res_ids_wo_stream)

                    # There should be a top-level heading on first page
                    has_top_level_heading = outlines_pages[0] == 0

                    if has_same_number_of_outlines and has_top_level_heading:
                        # Split the PDF according to outlines.
                        for i, num in enumerate(outlines_pages):
                            to = outlines_pages[i + 1] if i + 1 < len(outlines_pages) else reader.numPages
                            attachment_writer = PdfFileWriter()
                            for j in range(num, to):
                                attachment_writer.addPage(reader.getPage(j))
                            stream = io.BytesIO()
                            attachment_writer.write(stream)
                            collected_streams[res_ids_wo_stream[i]]['stream'] = stream

                        return collected_streams

                collected_streams[False] = {'stream': pdf_content_stream, 'attachment': None}

            return collected_streams
        
        res = super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids)
        
        if not res_ids:
            return res
        
        return res