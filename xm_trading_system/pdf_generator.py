"""
PDF Statement Generation for Zwesta Trading System
"""
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime
import os

class PDFStatementGenerator:
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.logo_path = "static/zwesta_logo.jpeg"
    
    def generate_statement(self, user_data, account_data, trades_data, period_type, period_start, period_end):
        """
        Generate PDF statement for user account
        period_type: 'daily', 'weekly', 'monthly', 'yearly'
        """
        filename = f"{account_data['account_name']}_{period_type}_{datetime.now().strftime('%Y%m%d')}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0096ff'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#0096ff'),
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        
        # Header with logo
        header_data = [['Logo', 'Zwesta Trading System\nPerformance Statement', 'Account Info']]
        header_table = Table(header_data, colWidths=[1.2*inch, 3.5*inch, 1.5*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 0), (1, 0), 16),
            ('TEXTCOLOR', (1, 0), (1, 0), colors.HexColor('#0096ff')),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Account and Period Info
        account_info = [
            ['Account Name:', account_data['account_name']],
            ['Account Type:', account_data['account_type'].upper()],
            ['Period:', f"{period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}"],
            ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['User:', user_data['full_name']],
        ]
        
        account_table = Table(account_info, colWidths=[2*inch, 3.5*inch])
        account_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
        ]))
        elements.append(account_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Summary Metrics
        elements.append(Paragraph("Performance Summary", heading_style))
        
        summary_data = [
            ['Metric', 'Value'],
            ['Opening Balance', f"${account_data['opening_balance']:,.2f}"],
            ['Closing Balance', f"${account_data['closing_balance']:,.2f}"],
            ['Profit/Loss', f"${account_data['profit_loss']:,.2f}"],
            ['Return %', f"{account_data['return_percent']:.2f}%"],
            ['Total Trades', str(account_data['total_trades'])],
            ['Winning Trades', str(account_data['winning_trades'])],
            ['Losing Trades', str(account_data['losing_trades'])],
            ['Win Rate', f"{account_data['win_rate']:.2f}%"],
            ['Largest Win', f"${account_data['largest_win']:,.2f}"],
            ['Largest Loss', f"${account_data['largest_loss']:,.2f}"],
        ]
        
        summary_table = Table(summary_data, colWidths=[2.5*inch, 2.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0096ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Trades Detail
        if trades_data:
            elements.append(Paragraph("Trade Details", heading_style))
            
            trades_table_data = [['Date', 'Symbol', 'Type', 'Entry Price', 'Exit Price', 'Qty', 'P&L', 'P&L %']]
            for trade in trades_data[:50]:  # Limit to 50 trades per page
                trades_table_data.append([
                    trade.get('date', ''),
                    trade.get('symbol', ''),
                    trade.get('type', ''),
                    f"${trade.get('entry_price', 0):.2f}",
                    f"${trade.get('exit_price', 0):.2f}" if trade.get('exit_price') else 'OPEN',
                    f"{trade.get('qty', 0):.2f}",
                    f"${trade.get('pnl', 0):,.2f}",
                    f"{trade.get('pnl_percent', 0):.2f}%"
                ])
            
            trades_table = Table(trades_table_data, colWidths=[0.9*inch, 0.8*inch, 0.6*inch, 1*inch, 1*inch, 0.6*inch, 0.8*inch, 0.8*inch])
            trades_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0096ff')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            ]))
            elements.append(trades_table)
        
        elements.append(Spacer(1, 0.2*inch))
        
        # Footer
        footer_text = f"<font size=8>Zwesta Trading System © 2026 | Confidential | Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</font>"
        elements.append(Paragraph(footer_text, styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        return filepath
