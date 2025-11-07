from typing import Dict, Any
from datetime import datetime
from app.models import Summary, Filing
import io
import csv
import re

class ExportService:
    def __init__(self):
        pass

    def generate_pdf_html(self, summary: Summary, filing: Filing) -> str:
        """Generate HTML for PDF export"""
        raw_summary = summary.raw_summary or {}
        sections = raw_summary.get("sections", {})
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #1f2937;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 40px 20px;
                }}
                h1 {{
                    color: #111827;
                    border-bottom: 3px solid #3b82f6;
                    padding-bottom: 10px;
                    margin-bottom: 30px;
                }}
                h2 {{
                    color: #1f2937;
                    margin-top: 30px;
                    margin-bottom: 15px;
                    border-bottom: 1px solid #e5e7eb;
                    padding-bottom: 5px;
                }}
                h3 {{
                    color: #374151;
                    margin-top: 20px;
                    margin-bottom: 10px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #e5e7eb;
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #f3f4f6;
                    font-weight: 600;
                }}
                .header {{
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #e5e7eb;
                }}
                .metadata {{
                    color: #6b7280;
                    font-size: 0.9em;
                    margin-bottom: 10px;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #e5e7eb;
                    color: #6b7280;
                    font-size: 0.85em;
                    text-align: center;
                }}
                ul {{
                    margin: 10px 0;
                    padding-left: 20px;
                }}
                li {{
                    margin: 5px 0;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{filing.company.name} - {filing.filing_type} Summary</h1>
                <div class="metadata">
                    <p><strong>Filing Date:</strong> {filing.filing_date.strftime('%B %d, %Y') if filing.filing_date else 'N/A'}</p>
                    <p><strong>Period End:</strong> {filing.period_end_date.strftime('%B %d, %Y') if filing.period_end_date else 'N/A'}</p>
                    <p><strong>Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                    <p><strong>Source:</strong> SEC EDGAR - {filing.sec_url}</p>
                </div>
            </div>
        """
        
        # Add executive snapshot
        if sections.get("executive_snapshot"):
            html += f"""
            <h2>Executive Assessment</h2>
            <div>{self._format_markdown(sections["executive_snapshot"])}</div>
            """
        
        # Add financial highlights table
        financial_highlights = sections.get("financial_highlights", {})
        if financial_highlights.get("table"):
            html += """
            <h2>Financial Highlights</h2>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Current Period</th>
                        <th>Prior Period</th>
                        <th>Investor Takeaway</th>
                    </tr>
                </thead>
                <tbody>
            """
            for row in financial_highlights["table"]:
                html += f"""
                    <tr>
                        <td>{row.get('metric', 'N/A')}</td>
                        <td>{row.get('current_period', 'N/A')}</td>
                        <td>{row.get('prior_period', 'N/A')}</td>
                        <td>{row.get('commentary', 'N/A')}</td>
                    </tr>
                """
            html += """
                </tbody>
            </table>
            """
        
        # Add management discussion
        if sections.get("management_discussion_insights"):
            html += f"""
            <h2>Management Strategy & Execution</h2>
            <div>{self._format_markdown(sections["management_discussion_insights"])}</div>
            """
        
        # Add risk factors
        risk_factors = sections.get("risk_factors", [])
        if risk_factors:
            html += """
            <h2>Investment Risks & Concerns</h2>
            <ul>
            """
            for risk in risk_factors[:15]:  # Limit to top 15
                if isinstance(risk, str):
                    html += f"<li>{risk}</li>"
                elif isinstance(risk, dict):
                    title = (risk.get("title") or "").strip()
                    description = (risk.get("description") or "").strip()
                    summary = (risk.get("summary") or "").strip()
                    evidence = risk.get("supporting_evidence") or risk.get("supportingEvidence") or risk.get("evidence")
                    if isinstance(evidence, (list, tuple, set)):
                        evidence = "; ".join(str(item).strip() for item in evidence if item)
                    elif isinstance(evidence, dict):
                        evidence = "; ".join(str(val).strip() for val in evidence.values() if val)
                    evidence = (evidence or "").strip()

                    if title and description:
                        body = f"<strong>{title}</strong>: {description}"
                    elif title and summary and summary.lower() != title.lower():
                        body = f"<strong>{title}</strong>: {summary}"
                    else:
                        body = summary or title or description

                    html += "<li>"
                    html += body or "Risk detail not provided"
                    if evidence:
                        html += f"<div><em>Evidence:</em> {evidence}</div>"
                    html += "</li>"
            html += "</ul>"
        
        # Add segment performance
        if sections.get("segment_performance"):
            html += f"""
            <h2>Business Segment Analysis</h2>
            <div>{self._format_markdown(sections["segment_performance"])}</div>
            """
        
        # Add guidance
        if sections.get("guidance_outlook"):
            html += f"""
            <h2>Forward Outlook & Investment Implications</h2>
            <div>{self._format_markdown(sections["guidance_outlook"])}</div>
            """
        
        # Add 3-year trend if available
        if sections.get("three_year_trend"):
            html += f"""
            <h2>3-Year Investment Perspective</h2>
            <div>{self._format_markdown(sections["three_year_trend"])}</div>
            """
        
        html += f"""
            <div class="footer">
                <p>Generated by EarningsNerd - AI-Powered SEC Filing Analysis</p>
                <p>This summary is derived from publicly available SEC filings and is for informational purposes only.</p>
            </div>
        </body>
        </html>
        """
        
        return html

    def _format_markdown(self, text: str) -> str:
        """Convert basic markdown to HTML"""
        if not text:
            return ""
        
        text = text.strip()
        if not text:
            return ""

        # Headings
        text = re.sub(r'(?m)^###\s*(.+)$', r'<h3>\1</h3>', text)
        text = re.sub(r'(?m)^##\s*(.+)$', r'<h2>\1</h2>', text)

        # Bold emphasis
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

        blocks = []
        for block in re.split(r'\n{2,}', text):
            block = block.strip()
            if not block:
                continue
            if block.startswith("<h2>") or block.startswith("<h3>"):
                blocks.append(block)
            else:
                block_html = block.replace('\n', '<br />')
                blocks.append(f"<p>{block_html}</p>")

        return "".join(blocks)

    def generate_csv(self, summary: Summary, filing: Filing) -> str:
        """Generate CSV export of financial metrics"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([f"{filing.company.name} - {filing.filing_type} Summary"])
        writer.writerow([f"Filing Date: {filing.filing_date.strftime('%Y-%m-%d') if filing.filing_date else 'N/A'}"])
        writer.writerow([f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
        writer.writerow([])
        
        # Financial highlights table
        raw_summary = summary.raw_summary or {}
        sections = raw_summary.get("sections", {})
        financial_highlights = sections.get("financial_highlights", {})
        
        if financial_highlights.get("table"):
            writer.writerow(["Financial Highlights"])
            writer.writerow(["Metric", "Current Period", "Prior Period", "Investor Takeaway"])
            
            for row in financial_highlights["table"]:
                writer.writerow([
                    row.get("metric", ""),
                    row.get("current_period", ""),
                    row.get("prior_period", ""),
                    row.get("commentary", "")
                ])
            writer.writerow([])
        
        # Risk factors
        risk_factors = sections.get("risk_factors", [])
        if risk_factors:
            writer.writerow(["#", "Risk", "Supporting Evidence"])
            for i, risk in enumerate(risk_factors[:15], 1):
                if isinstance(risk, str):
                    writer.writerow([i, risk, ""])
                elif isinstance(risk, dict):
                    title = (risk.get("title") or "").strip()
                    description = (risk.get("description") or "").strip()
                    summary = (risk.get("summary") or "").strip()
                    evidence = risk.get("supporting_evidence") or risk.get("supportingEvidence") or risk.get("evidence")
                    if isinstance(evidence, (list, tuple, set)):
                        evidence = "; ".join(str(item).strip() for item in evidence if item)
                    elif isinstance(evidence, dict):
                        evidence = "; ".join(str(val).strip() for val in evidence.values() if val)
                    evidence = (evidence or "").strip()

                    if title and description:
                        risk_text = f"{title}: {description}"
                    elif title and summary and summary.lower() != title.lower():
                        risk_text = f"{title}: {summary}"
                    else:
                        risk_text = summary or title or description

                    writer.writerow([i, risk_text, evidence])
        
        return output.getvalue()

    async def export_pdf(self, summary: Summary, filing: Filing) -> bytes:
        """Export summary as PDF"""
        try:
            from weasyprint import HTML
            html_content = self.generate_pdf_html(summary, filing)
            html = HTML(string=html_content)
            pdf_bytes = html.write_pdf()
            return pdf_bytes
        except ImportError:
            raise Exception("WeasyPrint is not installed. Install it with: pip install weasyprint")
        except Exception as e:
            raise Exception(f"Failed to generate PDF: {str(e)}")

export_service = ExportService()

