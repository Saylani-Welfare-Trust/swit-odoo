import os
import tempfile
from flask import Flask, request, jsonify
import win32print
import win32api
from flask_cors import CORS

# Flask app setup
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# logging setup
import logging
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

# Get the list of available printers
def get_available_printers():
    return [p[2] for p in win32print.EnumPrinters(
    win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
)]


# Get the default printer
def get_default_printer():
    try:
        return win32print.GetDefaultPrinter()
    except Exception:
        return None

# Map of printer status flags to human-readable descriptions
PRINTER_STATUS_FLAGS = {
    win32print.PRINTER_STATUS_OFFLINE: "Offline",
    win32print.PRINTER_STATUS_ERROR: "Error",
    win32print.PRINTER_STATUS_PAPER_OUT: "Paper out",
    win32print.PRINTER_STATUS_NO_TONER: "No toner",
    win32print.PRINTER_STATUS_DOOR_OPEN: "Door open",
    win32print.PRINTER_STATUS_NOT_AVAILABLE: "Not available",
    win32print.PRINTER_STATUS_BUSY: "Busy",
}   


def check_printer_ready(printer_name):
    """
    Check if the specified printer is ready.
    Returns (True, None) if printer is ready
    Returns (False, reason) if not
    """

    handle, status = None, 0
    error = None
    try:
        handle = win32print.OpenPrinter(printer_name)
        printer_info = win32print.GetPrinter(handle, 2)
        status = printer_info.get("Status", 0)
    except Exception as e:
        error = f"Printer query failed: {e}"
    finally:
        if handle:
            try:
                win32print.ClosePrinter(handle)
            except Exception:
                pass

    if error:
        return False, error

    # If status is 0, printer is ready
    if status == 0:
        return True, None

    # Collect reasons for non-ready status
    reasons = [
        desc for flag, desc in PRINTER_STATUS_FLAGS.items()
        if status & flag
    ]

    # Return not ready with reasons
    return False, ", ".join(reasons) or "Unknown printer issue"



def print_pdf(pdf_path, printer_name):
    """
    Print a PDF file to the specified printer.
    """

    # Validate printer
    if printer_name not in get_available_printers():
        raise ValueError(f"Printer '{printer_name}' not found")

    # Check if printer is ready
    ready, reason = check_printer_ready(printer_name)
    if not ready:
        raise RuntimeError(f"Printer '{printer_name}' is not ready: {reason}")

    # old default printer (may not exist)
    try:
        old_printer = win32print.GetDefaultPrinter()
    except Exception:
        old_printer = None

    # Set default printer temporarily (best-effort)
    try:
        try:
            win32print.SetDefaultPrinter(printer_name)
        except Exception:
            pass

        # Send PDF to printer via ShellExecute (relies on file association)
        win32api.ShellExecute(
            0,
            "print",
            pdf_path,
            None,
            ".",
            0
        )
    finally:
        if old_printer:
            try:
                win32print.SetDefaultPrinter(old_printer)
            except Exception:
                pass


@app.route("/print/pdf", methods=["POST"])
def print_pdf_api():
    """
    Print a PDF file sent in the request to the specified printer.
    Expects a multipart/form-data request with:
    - file: the PDF file to print
    - printer_name: (optional) name of the printer to use
    """
    
    if "file" not in request.files:
        return jsonify({"error": "PDF file missing"}), 400

    printer_name = request.form.get("printer_name")
    if not printer_name or (isinstance(printer_name, str) and printer_name.lower() == "null"):
        printer_name = get_default_printer()
    if not printer_name:
        return jsonify({"error": "No printer specified and no default printer available"}), 400

    pdf_file = request.files["file"]

    # Save the uploaded PDF to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf_file.save(tmp.name)
        pdf_path = tmp.name

    # Attempt to print the PDF
    try:
        print_pdf(pdf_path, printer_name)
        return jsonify({"status": "printed", "printer": printer_name})
    except ValueError as e:
        _logger.exception(e)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        _logger.exception(e)
        return jsonify({"error": f"Printing failed: {str(e)}"}), 500
    finally:
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass


@app.route("/print/text", methods=["POST"])
def print_text_api():
    """
    Print raw text to the specified printer.
    Expects a JSON request with:
    - text: the text to print
    - printer_name: (optional) name of the printer to use
    """
    
    data = request.json or {}
    text = data.get("text")

    if not text:
        return jsonify({"error": "text missing"}), 400

    printer_name = data.get("printer_name") or get_default_printer()
    if isinstance(printer_name, str) and printer_name.lower() == "null":
        printer_name = get_default_printer()
    if not printer_name:
        return jsonify({"error": "No printer specified and no default printer available"}), 400

    if printer_name not in get_available_printers():
        return jsonify({"error": f"Printer '{printer_name}' not found"}), 400

    hPrinter = None
    try:
        hPrinter = win32print.OpenPrinter(printer_name)
        hJob = win32print.StartDocPrinter(hPrinter, 1, ("Text Print", None, "RAW"))
        win32print.StartPagePrinter(hPrinter)
        win32print.WritePrinter(hPrinter, text.encode("utf-8", errors="replace"))
        win32print.EndPagePrinter(hPrinter)
        win32print.EndDocPrinter(hPrinter)
    finally:
        if hPrinter:
            try:
                win32print.ClosePrinter(hPrinter)
            except Exception:
                pass

    return jsonify({"status": "printed", "printer": printer_name})


# Run the Flask app
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)

