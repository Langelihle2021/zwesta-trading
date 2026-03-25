"""
WhatsApp Alert Service via Twilio
Sends trading alerts via WhatsApp notifications
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class WhatsAppAlertService:
    """
    Twilio WhatsApp integration for sending trading alerts
    Supports profit/loss alerts, position notifications, and system messages
    """

    def __init__(self,
                 account_sid: str,
                 auth_token: str,
                 from_number: str):
        """
        Initialize WhatsApp alert service
        
        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            from_number: Twilio WhatsApp number (format: whatsapp:+1234567890)
        """
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        
        self.is_configured = account_sid and auth_token
        
        if self.is_configured:
            try:
                # In production: from twilio.rest import Client
                # self.client = Client(account_sid, auth_token)
                logger.info("WhatsApp service initialized with Twilio")
            except Exception as e:
                logger.warning(f"Twilio client setup issue: {str(e)}")
        else:
            logger.warning("WhatsApp service not configured - alerts will be logged only")

    async def send_profit_alert(self,
                               to_number: str,
                               symbol: str,
                               profit: float,
                               profit_percent: float,
                               trade_type: str,
                               entry_price: float,
                               exit_price: float) -> bool:
        """
        Send profit alert via WhatsApp
        
        Args:
            to_number: Recipient WhatsApp number
            symbol: Trading symbol
            profit: Profit amount
            profit_percent: Profit percentage
            trade_type: BUY or SELL
            entry_price: Trade entry price
            exit_price: Trade exit price
        
        Returns:
            True if sent successfully
        """
        try:
            message = (
                f"🎉 *Profit Alert*\n\n"
                f"Symbol: {symbol}\n"
                f"Type: {trade_type}\n"
                f"Entry: ${entry_price:.4f}\n"
                f"Exit: ${exit_price:.4f}\n"
                f"Profit: ${profit:.2f} ({profit_percent:.2f}%)\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            return await self._send_whatsapp(to_number, message)
        
        except Exception as e:
            logger.error(f"Failed to send profit alert: {str(e)}")
            return False

    async def send_loss_alert(self,
                             to_number: str,
                             symbol: str,
                             loss: float,
                             loss_percent: float,
                             trade_type: str,
                             entry_price: float,
                             exit_price: float) -> bool:
        """Send loss alert via WhatsApp"""
        try:
            message = (
                f"⚠️ *Loss Alert*\n\n"
                f"Symbol: {symbol}\n"
                f"Type: {trade_type}\n"
                f"Entry: ${entry_price:.4f}\n"
                f"Exit: ${exit_price:.4f}\n"
                f"Loss: ${loss:.2f} ({loss_percent:.2f}%)\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            return await self._send_whatsapp(to_number, message)
        
        except Exception as e:
            logger.error(f"Failed to send loss alert: {str(e)}")
            return False

    async def send_position_alert(self,
                                 to_number: str,
                                 symbol: str,
                                 position_type: str,
                                 volume: float,
                                 entry_price: float,
                                 stop_loss: float,
                                 take_profit: float) -> bool:
        """Send position opened alert via WhatsApp"""
        try:
            message = (
                f"📊 *Position Opened*\n\n"
                f"Symbol: {symbol}\n"
                f"Type: {position_type}\n"
                f"Volume: {volume} lots\n"
                f"Entry: ${entry_price:.4f}\n"
                f"SL: ${stop_loss:.4f}\n"
                f"TP: ${take_profit:.4f}\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            return await self._send_whatsapp(to_number, message)
        
        except Exception as e:
            logger.error(f"Failed to send position alert: {str(e)}")
            return False

    async def send_margin_alert(self,
                               to_number: str,
                               account_balance: float,
                               margin_level: float,
                               free_margin: float) -> bool:
        """Send margin call warning via WhatsApp"""
        try:
            message = (
                f"⚡ *Margin Alert*\n\n"
                f"Balance: ${account_balance:.2f}\n"
                f"Margin Level: {margin_level:.2f}%\n"
                f"Free Margin: ${free_margin:.2f}\n"
                f"⚠️ Margin level is critically low!\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            return await self._send_whatsapp(to_number, message)
        
        except Exception as e:
            logger.error(f"Failed to send margin alert: {str(e)}")
            return False

    async def send_signal_alert(self,
                               to_number: str,
                               symbol: str,
                               signal_type: str,
                               confidence: float,
                               details: str = "") -> bool:
        """Send trading signal alert via WhatsApp"""
        try:
            emoji = "📈" if signal_type.upper() == "BUY" else "📉"
            message = (
                f"{emoji} *{signal_type.upper()} Signal*\n\n"
                f"Symbol: {symbol}\n"
                f"Confidence: {confidence:.1%}\n"
            )
            
            if details:
                message += f"Details: {details}\n"
            
            message += f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            
            return await self._send_whatsapp(to_number, message)
        
        except Exception as e:
            logger.error(f"Failed to send signal alert: {str(e)}")
            return False

    async def send_custom_alert(self,
                               to_number: str,
                               title: str,
                               message: str) -> bool:
        """Send custom message via WhatsApp"""
        try:
            full_message = f"*{title}*\n\n{message}"
            return await self._send_whatsapp(to_number, full_message)
        
        except Exception as e:
            logger.error(f"Failed to send custom alert: {str(e)}")
            return False

    async def _send_whatsapp(self, to_number: str, message: str) -> bool:
        """
        Internal method to send WhatsApp message
        
        Args:
            to_number: Recipient number
            message: Message content
        
        Returns:
            True if sent successfully
        """
        try:
            formatted_number = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number
            
            # In production:
            # message = self.client.messages.create(
            #     from_=self.from_number,
            #     to=formatted_number,
            #     body=message
            # )
            # return message.sid is not None
            
            # For now, log the message
            logger.info(f"WhatsApp alert to {formatted_number}:\n{message}")
            return True
        
        except Exception as e:
            logger.error(f"WhatsApp send failed: {str(e)}")
            return False

    async def send_daily_report(self,
                               to_number: str,
                               trades_total: int,
                               trades_winning: int,
                               total_profit: float,
                               win_rate: float,
                               account_balance: float) -> bool:
        """Send daily trading report via WhatsApp"""
        try:
            message = (
                f"📈 *Daily Trading Report*\n\n"
                f"Trades: {trades_total}\n"
                f"Winning: {trades_winning}\n"
                f"Win Rate: {win_rate:.1%}\n"
                f"Profit: ${total_profit:.2f}\n"
                f"Balance: ${account_balance:.2f}\n"
                f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}"
            )
            
            return await self._send_whatsapp(to_number, message)
        
        except Exception as e:
            logger.error(f"Failed to send daily report: {str(e)}")
            return False
