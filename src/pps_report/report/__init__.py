"""
Report generation modules.
"""

from pps_report.report.core.html_pdf_generator import HTMLPDFGenerator

PDFGenerator = HTMLPDFGenerator

__all__ = ['PDFGenerator', 'HTMLPDFGenerator']
