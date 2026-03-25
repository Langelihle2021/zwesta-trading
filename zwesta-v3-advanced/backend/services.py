import requests
import json
from typing import List, Dict
from config import get_settings
from twilio.rest import Client

settings = get_settings()

# ===== Crypto Price Service =====
class CryptoService:
    @staticmethod
    async def get_crypto_price(symbol: str) -> Dict:
        """Get real-time crypto price from CoinGecko"""
        try:
            symbol_map = {
                "BTC": "bitcoin",
                "ETH": "ethereum",
                "BNB": "binancecoin",
                "ADA": "cardano",
                "XRP": "ripple",
                "SOL": "solana",
            }
            
            gecko_id = symbol_map.get(symbol, symbol.lower())
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": gecko_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true"
            }
            
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                price_data = data.get(gecko_id, {})
                return {
                    "symbol": symbol,
                    "price": price_data.get("usd", 0),
                    "change_24h": price_data.get("usd_24h_change", 0)
                }
            return {"symbol": symbol, "price": 0, "change_24h": 0}
        except Exception as e:
            return {"symbol": symbol, "price": 0, "change_24h": 0, "error": str(e)}

    @staticmethod
    async def get_forex_price(symbol: str) -> Dict:
        """Get forex price (demo data)"""
        forex_data = {
            "EURUSD": {"price": 1.0980, "change_24h": 0.15},
            "GBPUSD": {"price": 1.2730, "change_24h": -0.22},
            "USDJPY": {"price": 149.50, "change_24h": 0.45},
            "AUDUSD": {"price": 0.6540, "change_24h": 0.30},
        }
        return {
            "symbol": symbol,
            **forex_data.get(symbol, {"price": 0, "change_24h": 0})
        }

# ===== WhatsApp Alert Service =====
class AlertService:
    @staticmethod
    async def send_whatsapp_alert(phone: str, message: str):
        """Send WhatsApp alert via Twilio"""
        try:
            if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
                return {"status": "demo", "message": "Twilio not configured"}
            
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            msg = client.messages.create(
                from_=f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}",
                body=message,
                to=f"whatsapp:{phone}"
            )
            return {"status": "sent", "sid": msg.sid}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    @staticmethod
    async def send_profit_alert(user_phone: str, pnl: float, symbol: str):
        """Send profit alert"""
        message = f"🎉 Zwesta Trading Alert\n\n✅ Position closed on {symbol}\n💰 Profit: ${pnl:.2f}\n\nKeep trading! 📈"
        return await AlertService.send_whatsapp_alert(user_phone, message)

# ===== PDF Report Service =====
class ReportService:
    @staticmethod
    def generate_trading_report(account_data: Dict, trades: List[Dict]) -> bytes:
        """Generate PDF trading report"""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from io import BytesIO
        from datetime import datetime
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f77b4'),
            spaceAfter=30,
        )
        elements.append(Paragraph("Trading Report", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Account Info
        account_table = Table([
            ["Account", account_data.get("name", "Demo Account")],
            ["Period", f"{datetime.now().strftime('%Y-%m-%d')}"],
            ["Total Trades", str(len(trades))],
            ["Total P&L", f"${sum(t.get('pnl', 0) for t in trades):.2f}"],
            ["Win Rate", f"{(len([t for t in trades if t.get('pnl', 0) > 0]) / len(trades) * 100) if trades else 0:.1f}%"],
        ])
        account_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(account_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Trades Table
        trade_data = [["Symbol", "Type", "Entry", "Exit", "P&L", "P&L %"]]
        for trade in trades[:20]:  # Limit to 20 trades
            trade_data.append([
                trade.get("symbol", "N/A"),
                trade.get("type", "N/A"),
                f"${trade.get('entry_price', 0):.2f}",
                f"${trade.get('exit_price', 0):.2f}",
                f"${trade.get('pnl', 0):.2f}",
                f"{trade.get('pnl_percent', 0):.2f}%",
            ])
        
        trades_table = Table(trade_data)
        trades_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(trades_table)
        
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

# ===== Payment Service =====
class PaymentService:
    @staticmethod
    async def process_deposit(amount: float, card_token: str) -> Dict:
        """Process deposit via Stripe"""
        try:
            if not settings.STRIPE_API_KEY:
                return {"status": "demo", "message": "Stripe not configured", "amount": amount}
            
            import stripe
            stripe.api_key = settings.STRIPE_API_KEY
            
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency="usd",
                payment_method=card_token,
                confirm=True,
            )
            
            return {"status": "confirmed", "amount": amount, "id": intent.id}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

# ===== Trading Bot Service =====
class BotService:
    @staticmethod
    async def check_trading_opportunities(symbol: str, strategy: str) -> Dict:
        """Check trading opportunities based on strategy"""
        # This is demo logic - replace with actual strategy
        crypto_price = await CryptoService.get_crypto_price(symbol.split("USD")[0])
        
        return {
            "symbol": symbol,
            "strategy": strategy,
            "signal": "buy" if crypto_price.get("change_24h", 0) > 0.5 else "sell",
            "confidence": 0.75,
            "price": crypto_price.get("price", 0),
            "timestamp": datetime.now().isoformat()
        }

from datetime import datetime
