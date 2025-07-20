import os
import sys
import smtplib
import imaplib
import email
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import feedparser
import google.generativeai as genai
from typing import List, Dict, Optional
import json
import logging
from dataclasses import dataclass
import time
import schedule
import pytz
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
@dataclass
class NewsItem:
    title: str
    summary: str
    source: str
    url: str
@dataclass
class EmailItem:
    sender: str
    subject: str
    date: str
    snippet: str
@dataclass
class WeatherInfo:
    temperature: float
    description: str
    humidity: int
    wind_speed: float
    feels_like: float
class MorningBriefingAgent:
    def __init__(self, config_file: str = "config.json"):
        self.config = self.load_config(config_file)
        genai.configure(api_key=self.config["gemini_api_key"])
        self.gemini_model = None
        self.model_name = None
        self._initialize_gemini_model()
    def _initialize_gemini_model(self):
        model_names = [
            'gemini-1.5-flash', 'gemini-1.5-pro',
            'gemini-pro','models/gemini-1.5-flash',
            'models/gemini-1.5-pro','models/gemini-pro']
        for model_name in model_names:
            try:
                self.gemini_model = genai.GenerativeModel(model_name)
                test_response = self.gemini_model.generate_content("Hello")
                if test_response.text:
                    self.model_name = model_name
                    logger.info(f"Successfully initialized Gemini model: {model_name}")
                    return
            except Exception as e:
                logger.debug(f"Failed to initialize model {model_name}: {e}")
                continue        
        logger.warning("Could not initialize any Gemini model")
        self.gemini_model = None
        self.model_name = None
    def list_available_models(self):
        try:
            logger.info("Listing available Gemini models...")
            for model in genai.list_models():
                if 'generateContent' in model.supported_generation_methods:
                    logger.info(f"Available model: {model.name}")
        except Exception as e:
            logger.error(f"Error listing models: {e}")    
    def load_config(self, config_file: str) -> Dict:
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file {config_file} not found. Creating template...")
            self.create_config_template(config_file)
            raise Exception("Please fill in the config.json file with your API keys and credentials")
    def create_config_template(self, config_file: str):
        template = {
            "gemini_api_key": "your-gemini-api-key",
            "openweather_api_key": "your-openweather-api-key",
            "gmail_email": "your-gmail@gmail.com",
            "gmail_password": "your-gmail-app-password",
            "recipient_email": "recipient@email.com",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "imap_server": "imap.gmail.com",
            "city": "Delhi",
            "country_code": "IN"
        }
        with open(config_file, 'w') as f:
            json.dump(template, f, indent=4)
    def fetch_bbc_news(self, limit: int = 9) -> List[NewsItem]:
        try:
            logger.info("Fetching BBC news...")
            feed = feedparser.parse("http://feeds.bbci.co.uk/news/rss.xml")
            news_items = []
            for entry in feed.entries[:limit]:
                news_items.append(NewsItem(
                    title=entry.title,
                    summary=entry.summary if hasattr(entry, 'summary') else entry.title,
                    source="BBC",
                    url=entry.link))
            logger.info(f"Retrieved {len(news_items)} BBC news items")
            return news_items
        except Exception as e:
            logger.error(f"Error fetching BBC news: {e}")
            return []
    def fetch_times_of_india_news(self, limit: int = 9) -> List[NewsItem]:
        try:
            logger.info("Fetching Times of India news...")
            feed = feedparser.parse("https://timesofindia.indiatimes.com/rssfeedstopstories.cms")
            news_items = []            
            for entry in feed.entries[:limit]:
                news_items.append(NewsItem(
                    title=entry.title,
                    summary=entry.summary if hasattr(entry, 'summary') else entry.title,
                    source="Times of India",
                    url=entry.link))
            logger.info(f"Retrieved {len(news_items)} Times of India news items")
            return news_items
        except Exception as e:
            logger.error(f"Error fetching Times of India news: {e}")
            return []
    def fetch_weather(self) -> Optional[WeatherInfo]:
        try:
            logger.info("Fetching weather information...")
            url = f"http://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": f"{self.config['city']},{self.config['country_code']}",
                "appid": self.config["openweather_api_key"],
                "units": "metric"
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()            
            if "cod" in data and data["cod"] != 200:
                raise Exception(f"OpenWeatherMap API error: {data.get('message', 'Unknown error')}")
            weather = WeatherInfo(
                temperature=data["main"]["temp"],
                description=data["weather"][0]["description"].title(),
                humidity=data["main"]["humidity"],
                wind_speed=data["wind"]["speed"],
                feels_like=data["main"]["feels_like"])
            logger.info("Weather information retrieved successfully")
            return weather
        except Exception as e:
            logger.error(f"Error fetching weather: {e}")
            return None
    def fetch_recent_emails(self, days: int = 1, limit: int = 10) -> List[EmailItem]:
        try:
            logger.info("Fetching recent emails...")            
            mail = imaplib.IMAP4_SSL(self.config["imap_server"])
            mail.login(self.config["gmail_email"], self.config["gmail_password"])
            mail.select("inbox")
            since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
            result, data = mail.search(None, f'(UNSEEN SINCE {since_date})')            
            email_items = []
            if data[0]:
                email_ids = data[0].split()[-limit:]
                for email_id in email_ids:
                    result, msg_data = mail.fetch(email_id, "(RFC822)")
                    if result == "OK":
                        msg = email.message_from_bytes(msg_data[0][1])                        
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8")                        
                        sender = msg.get("From", "Unknown")                        
                        date_str = msg.get("Date", "Unknown")                        
                        snippet = self.extract_email_snippet(msg)
                        email_items.append(EmailItem(
                            sender=sender,
                            subject=subject,
                            date=date_str,
                            snippet=snippet))
            mail.close()
            mail.logout()
            logger.info(f"Retrieved {len(email_items)} recent emails")
            return email_items
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []
    def extract_email_snippet(self, msg, max_length: int = 150) -> str:
        try:
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            snippet = body.strip().replace("\n", " ").replace("\r", " ")
            if len(snippet) > max_length:
                snippet = snippet[:max_length] + "..."
            return snippet or "No content preview available"
        except Exception as e:
            logger.error(f"Error extracting email snippet: {e}")
            return "Content preview unavailable"    
    def generate_briefing(self, news_items: List[NewsItem], weather: Optional[WeatherInfo], 
                         emails: List[EmailItem]) -> str:
        try:
            logger.info("Generating morning briefing...")            
            current_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")            
            news_text = ""
            if news_items:
                news_text = "NEWS HEADLINES:\n"
                for item in news_items:
                    news_text += f"- {item.title} ({item.source})\n"            
            weather_text = ""
            if weather:
                weather_text = f"WEATHER IN DELHI:\n"
                weather_text += f"Temperature: {weather.temperature}°C (feels like {weather.feels_like}°C)\n"
                weather_text += f"Condition: {weather.description}\n"
                weather_text += f"Humidity: {weather.humidity}%\n"
                weather_text += f"Wind Speed: {weather.wind_speed} m/s\n"            
            email_text = ""
            if emails:
                email_text = f"RECENT EMAILS ({len(emails)} unread):\n"
                for email_item in emails:
                    email_text += f"- From: {email_item.sender}\n"
                    email_text += f"  Subject: {email_item.subject}\n"
                    email_text += f"  Preview: {email_item.snippet}\n\n"
            else:
                email_text = "EMAILS: No new correspondence has arrived this morning.\n"
            prompt = f"""You are Jarvis, a distinguished British butler with impeccable manners and eloquent speech. 
            Your task is to prepare a charming morning briefing for your employer. 
            
            Current time: {current_time}
            
            Please compose an elegant, informative, and slightly witty morning briefing that includes:
            
            {news_text}
            
            {weather_text}
            
            {email_text}
            
            Format this as a proper butler's briefing with:
            - A courteous greeting
            - Well-organized sections for news, weather, and emails
            - Sophisticated language and subtle British humor
            - Practical advice or observations where appropriate
            - A polite closing
            
            IMPORTANT FORMATTING RULES:
            - Do NOT use any markdown formatting like ** or * for bold text
            - Do NOT include placeholder text like "Jarvis would then..." or similar
            - Write in plain text only
            - If there are emails, provide actual summaries, not placeholders
            - If there are no emails, simply state "No new correspondence has arrived this morning, sir"
            - Keep the tone professional yet warm, and make it engaging to read over morning coffee
            
            Write the complete briefing without any placeholders or markdown formatting."""            
            if self.gemini_model is None:
                logger.warning("No Gemini model available, using fallback briefing")
                return self.create_fallback_briefing(news_items, weather, emails)
            try:
                response = self.gemini_model.generate_content(prompt)
                if response.text:
                    briefing = response.text
                    logger.info(f"Morning briefing generated successfully using Gemini ({self.model_name})")
                    return briefing
                else:
                    logger.warning("Gemini returned empty response")
                    return self.create_fallback_briefing(news_items, weather, emails)
            except Exception as gemini_error:
                logger.warning(f"Error with Gemini API: {gemini_error}")
                logger.warning("Gemini API failed, creating basic briefing")
                return self.create_fallback_briefing(news_items, weather, emails)
        except Exception as e:
            logger.error(f"Error generating briefing: {e}")
            return self.create_fallback_briefing(news_items, weather, emails)    
    def create_fallback_briefing(self, news_items: List[NewsItem], weather: Optional[WeatherInfo], 
                                emails: List[EmailItem]) -> str:
        current_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        briefing = f"""Good morning!\n\nYour Morning Briefing for {current_time}\n\n"""        
        if news_items:
            briefing += "NEWS HEADLINES:\n"
            briefing += "=" * 10 + "\n"
            for item in news_items:
                briefing += f"• {item.title}\n"
                briefing += f"  Source: {item.source}\n\n"
        else:
            briefing += "NEWS: No news items available at this time.\n\n"        
        if weather:
            briefing += "WEATHER IN DELHI:\n"
            briefing += "=" * 10 + "\n"
            briefing += f"Temperature: {weather.temperature}°C (feels like {weather.feels_like}°C)\n"
            briefing += f"Condition: {weather.description}\n"
            briefing += f"Humidity: {weather.humidity}%\n"
            briefing += f"Wind Speed: {weather.wind_speed} m/s\n\n"
        else:
            briefing += "WEATHER: Weather information unavailable.\n\n"        
        if emails:
            briefing += f"RECENT EMAILS ({len(emails)} unread):\n"
            briefing += "=" * 10 + "\n"
            for email_item in emails:
                briefing += f"• From: {email_item.sender}\n"
                briefing += f"  Subject: {email_item.subject}\n"
                briefing += f"  Preview: {email_item.snippet}\n\n"
        else:
            briefing += "EMAILS: No new emails found.\n\n"
        briefing += "Have a wonderful day.\n"
        briefing += "\n---\n"
        briefing += "Kindly note that this is just a basic briefing. For AI-enhanced briefings, please check your Gemini API configuration."
        return briefing    
    def send_email(self, subject: str, body: str):
        try:
            logger.info("Sending briefing email...")
            msg = MIMEMultipart()
            msg['From'] = self.config["gmail_email"]
            msg['To'] = self.config["recipient_email"]
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            server = smtplib.SMTP(self.config["smtp_server"], self.config["smtp_port"])
            server.starttls()
            server.login(self.config["gmail_email"], self.config["gmail_password"])
            text = msg.as_string()
            server.sendmail(self.config["gmail_email"], self.config["recipient_email"], text)
            server.quit()
            logger.info("Briefing email sent successfully")
        except Exception as e:
            logger.error(f"Error sending email: {e}")    
    def check_api_health(self) -> Dict[str, bool]:
        health_status = {"gemini": False, "weather": False, "gmail": False}        
        try:
            if self.gemini_model is None:
                logger.warning("Gemini API: Failed - No model initialized")
                health_status["gemini"] = False
            else:
                test_response = self.gemini_model.generate_content("Hello, how are you?")
                if test_response.text:
                    health_status["gemini"] = True
                    logger.info(f"Gemini API: Working (using {self.model_name})")
                else:
                    logger.warning("Gemini API: Failed - Empty response")
        except Exception as e:
            logger.warning(f"Gemini API: Failed - {e}")
            logger.info("Attempting to reinitialize Gemini model...")
            self._initialize_gemini_model()
            if self.gemini_model is not None:
                try:
                    test_response = self.gemini_model.generate_content("Hello")
                    if test_response.text:
                        health_status["gemini"] = True
                        logger.info(f"Gemini API: Working after reinitialize (using {self.model_name})")
                except Exception as reinit_error:
                    logger.warning(f"Gemini API: Still failed after reinitialize - {reinit_error}")        
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": "Delhi,IN",
                "appid": self.config["openweather_api_key"],
                "units": "metric"}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                health_status["weather"] = True
                logger.info("Weather API: Working")
            else:
                logger.warning(f"Weather API: Failed - Status {response.status_code}")
        except Exception as e:
            logger.warning(f"Weather API: Failed - {e}")        
        try:
            mail = imaplib.IMAP4_SSL(self.config["imap_server"])
            mail.login(self.config["gmail_email"], self.config["gmail_password"])
            mail.select("inbox")
            mail.close()
            mail.logout()
            health_status["gmail"] = True
            logger.info("Gmail API: Working")
        except Exception as e:
            logger.warning(f"Gmail API: Failed - {e}")
        return health_status    
    def run_daily_briefing(self):
        try:
            logger.info("Starting daily briefing generation...")            
            health = self.check_api_health()
            logger.info(f"API Health Status: {health}")
            bbc_news = self.fetch_bbc_news(limit=9)
            toi_news = self.fetch_times_of_india_news(limit=9)
            all_news = bbc_news + toi_news
            logger.info(f"Total news articles fetched: {len(all_news)} (BBC: {len(bbc_news)}, TOI: {len(toi_news)})")
            weather = self.fetch_weather() if health["weather"] else None
            emails = self.fetch_recent_emails(days=1, limit=5) if health["gmail"] else []            
            briefing = self.generate_briefing(all_news, weather, emails)
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            subject = f"Your Morning Briefing - {current_date}"
            self.send_email(subject, briefing)
            logger.info("Daily briefing completed successfully")
        except Exception as e:
            logger.error(f"Error in daily briefing: {e}")
            error_subject = "Morning Briefing - Error Occurred"
            error_body = f"Good morning. I regret to inform you that an error occurred while preparing your briefing: {str(e)}"
            self.send_email(error_subject, error_body)
    def schedule_daily_briefing(self):
        ist = pytz.timezone('Asia/Kolkata')
        schedule.every().day.at("07:00").do(self.run_daily_briefing)
        logger.info("Daily briefing scheduled for 7:00 AM IST")
        logger.info("Waiting for scheduled time...")
        while True:
            schedule.run_pending()
            time.sleep(60) 
def main():
    agent = MorningBriefingAgent()
    if len(sys.argv) > 1 and sys.argv[1] == "--schedule":
        print("Starting scheduled mode, briefing will be sent at 7:00 AM IST daily...")
        agent.schedule_daily_briefing()
    else:
        print("Running briefing immediately...")
        agent.run_daily_briefing()
if __name__ == "__main__":
    main()
