from email.mime.text import MIMEText
import smtplib
from dotenv import load_dotenv
import time

load_dotenv()
import os


class ApprovalEmailer:
    
    def __init__(self, to_email):
        self.EMAIL = os.getenv("SUPER_ADMIN_EMAIL")
        self.APP_PASSWORD = os.getenv("SUPER_ADMIN_APP_PASSWORD")
        self.TO_EMAIL = to_email
        self.FROM_NAME = "Sales and Inventory AI tracking System"
        self.subject = "User Approval"
    
    def prepare_message(self) -> MIMEText:
        
        msg = MIMEText("html_body", "html")
        msg['from'] = f"{self.FROM_NAME} <{self.EMAIL}>"
        msg['To'] = self.TO_EMAIL
        msg['Subject'] = self.subject
        return msg
    
    def send(self):
        msg = self.prepare_message()
        
        for _ in range(5):
            try:
            
 
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as conn:
                    conn.login(self.EMAIL, self.APP_PASSWORD)
                    conn.sendmail(from_addr=self.EMAIL,to_addrs=self.TO_EMAIL, msg=msg.as_string())
                    break
            except Exception as e:
                 time.sleep(10)