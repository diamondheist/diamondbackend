import os
import json
import logging
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, Update
import firebase_admin
from firebase_admin import credentials, firestore

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Fetch Telegram Bot Token and Firebase Configuration
try:
    API_TOKEN = os.environ.get("BOT_TOKEN")
    FIREBASE_CONFIG = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    
    if not API_TOKEN or not FIREBASE_CONFIG:
        raise ValueError("Missing required environment variables")
    
    bot = AsyncTeleBot(API_TOKEN)
    
    # Initialize Firebase Admin (Firestore only, no Firebase Storage)
    firebase_config_dict = json.loads(FIREBASE_CONFIG)
    cred = credentials.Certificate(firebase_config_dict)
    firebase_admin.initialize_app(cred)
    
    db = firestore.client()

except Exception as e:
    logger.error(f"Initialization error: {e}")
    raise

def generate_start_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Open Diamondapp", web_app=WebAppInfo(url="https://diamondheist.netlify.app/")))
    return keyboard

@bot.message_handler(commands=['start'])
async def start(message):
    try:
        user_id = str(message.from_user.id)
        user_first_name = str(message.from_user.first_name)
        user_last_name = message.from_user.last_name or ''
        user_username = message.from_user.username or ''
        user_language_code = str(message.from_user.language_code or 'unknown')
        is_premium = message.from_user.is_premium or False
        text = message.text.split()

        welcome_message = (
            f"Hi, {user_first_name}! \n\n" 
            f"Welcome to DiamondHeist! \n\n"
            f"Here you can earn coins by mining them!\n\n"
            f"Invite friends to earn more coins together, and level up faster!")

        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            user_image = None  # No Firebase Storage usage here

            user_data = {
                'userImage': user_image,
                'firstName': user_first_name,
                'lastName': user_last_name,
                'userName': user_username,
                'languageCode': user_language_code,
                'isPremium': is_premium,
                'referrals': {},
                'balance': 0,
                'mineRate': 0.001,
                'isMining': False,
                'miningStartedTime': None,
                'daily': {
                    'claimedTime': None,
                    'claimDay': 0
                },
                'links': None,
            }

            if len(text) > 1 and text[1].startswith('ref_'):
                referrer_id = text[1][4:]
                referrer_ref = db.collection('users').document(referrer_id)
                referrer_doc = referrer_ref.get()

                if referrer_doc.exists:
                    user_data['referredBy'] = referrer_id
                    referrer_data = referrer_doc.to_dict()
                    bonus_amount = 500 if is_premium else 100

                    current_balance = referrer_data.get('balance', 0)
                    new_balance = current_balance + bonus_amount

                    referrals = referrer_data.get('referrals', {})
                    referrals[user_id] = {
                        'addedValue': bonus_amount,
                        'firstName': user_first_name,
                        'lastName': user_last_name,
                        'userImage': user_image,
                    }

                    referrer_ref.update({
                        'balance': new_balance,
                        'referrals': referrals
                    })
                else:
                    user_data['referredBy'] = None

                user_ref.set(user_data)

            keyboard = generate_start_keyboard()
            await bot.reply_to(message, welcome_message, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        error_message = "An error occurred. Please try again later."
        await bot.reply_to(message, error_message)

# Replace HTTP server with more robust webhook handling
async def process_webhook_update(update_dict):
    try:
        update = Update.de_json(update_dict)
        await bot.process_new_update([update])
    except Exception as e:
        logger.error(f"Webhook update processing error: {e}")

def set_webhook():
    webhook_url = os.environ.get('WEBHOOK_URL')  # This should be the full URL of your webhook handler (e.g., https://yourdomain.vercel.app/api/webhook)
    if webhook_url:
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    else:
        logger.error("Webhook URL not provided")

def main():
    logger.info("Telegram Bot is starting...")
    set_webhook()

if __name__ == "__main__":
    main()
