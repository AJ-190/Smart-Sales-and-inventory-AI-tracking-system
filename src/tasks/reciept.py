
import logging
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from src.tasks.debt_reminders import send_sms
from src.analytics.service import get_summary
from src.config import get_settings
from datetime import datetime


load_dotenv()
logger = logging.getLogger(__name__)


class RecieptReportGenerator:
    def __init__(
        self,
        phone: str,
        current_user,
        session,
        start_date: datetime,
        end_date: datetime,
        title: str = "Sales Summary",
    ):
        self.phone = phone
        self.current_user = current_user
        self.session = session
        self.start_date = start_date
        self.end_date = end_date
        self.title = title

    async def build_analytics_message(self) -> str:
        """Render the analytics summary as an SMS business report."""

        summary = await get_summary(
            self.current_user.business_id,
            self.session,
            self.current_user,
            date=self.start_date.date(),
            end_date=self.end_date.date()
        )


        total_sales = summary.get("total_sales", 0)
        total_revenue = summary.get("total_revenue", 0.0)
        total_profit = summary.get("total_profit", 0.0)
        sold_quantity = summary.get("sold_quantity", 0)
        cash_total = summary.get("cash_total", 0)
        momo_total = summary.get("momo_total", 0)
        card_total = summary.get("card_total", 0)
        best_product = summary.get("best_selling_product") or "N/A"

        if total_sales == 0 and total_profit == 0:
            return (
                f"AUTOMATED REPORT\n"
                f"{self.title} | {self.start_date.strftime('%b %d')} - {self.end_date.strftime('%b %d, %Y')}\n"
                f"\n"
                f"No sales data available for this period.\n"
                f"\n"
                f"This is an automated report from your Business Bot GH."
            )

        start_str = self.start_date.strftime("%b %d")
        end_str = self.end_date.strftime("%b %d, %Y")

        return (
            f"AUTOMATED REPORT\n"
            f"{self.title} | {start_str} - {end_str}\n"
            f"\n"
            f"Total Revenue: GHS {total_revenue:,.2f}\n"
            f"Total Profit: GHS {total_profit:,.2f}\n"
            f"Total Orders: {total_sales}\n"
            f"Units Sold: {sold_quantity}\n"
            f"\n"
            f"Payment breakdown\n"
            f"Cash: {cash_total}\n"
            f"Mobile money: {momo_total}\n"
            f"Card: {card_total}\n"
            f"\n"
            f"Best selling product: {best_product}\n"
            f"\n"
            f"This is an automated report from your Business Bot GH."
        )

    async def send_report_smss(self) -> bool:

        settings = get_settings()

        if not settings.sms_configured:
            logger.error(
                "SAILUP_API_KEY or SAILUP_SENDER_ID is not configured."
            )
            return False

        try:
            message = await self.build_analytics_message()
            success = await send_sms(self.phone, message)

            if success:
                logger.info(f"SMS report sent successfully to {self.phone}.")
                return True

            logger.error(f"Failed to send SMS report to {self.phone}.")
            return False

        except Exception as e:
            logger.error(f"Error sending report SMS to {self.phone}: {e}", exc_info=True)
            return False


    def render_receipt_reportlab(self, path, business, items, total):
        c = canvas.Canvas(path, pagesize=A4)
        width, height = A4

        c.setFont("Helvetica-Bold", 16)
        c.drawString(20 * mm, height - 25 * mm, business["name"])
        c.setFont("Helvetica", 9)
        c.drawString(20 * mm, height - 32 * mm, business["phone"])

        y = height - 50 * mm
        c.setFont("Helvetica-Bold", 9)
        c.drawString(20 * mm, y, "ITEM")
        c.drawRightString(width - 20 * mm, y, "SUBTOTAL")

        c.setFont("Helvetica", 9.5)
        for item in items:
            y -= 7 * mm
            c.drawString(20 * mm, y, item["name"])
            c.drawRightString(width - 20 * mm, y, f"GHS {item['qty'] * item['unit_price']:.2f}")

        y -= 12 * mm
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(width - 20 * mm, y, f"Total: GHS {total:.2f}")

        c.setFont("Helvetica", 7)
        c.drawCentredString(width / 2, 15 * mm, f"{business['name']} · generated via Business Bot")
        c.save()
