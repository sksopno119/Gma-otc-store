from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import json
import asyncio
import logging
import os  # নতুন ইম্পোর্ট
import psycopg2  # নতুন ইম্পোর্ট
from dotenv import load_dotenv  # নতুন ইম্পোর্ট
from datetime import datetime, timedelta # এটি আপনার কোডে ছিল

# .env ফাইল থেকে ভেরিয়েবল লোড করার চেষ্টা (Render-এর জন্য জরুরি নয়, কিন্তু ভালো অভ্যাস)
load_dotenv()

# Render-এর Environment Variables থেকে টোকেন এবং আইডি লোড করা
TOKEN = os.environ.get('TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 5810613583)) # আপনার অ্যাডমিন আইডি

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- নতুন ডাটাবেস ফাংশন ---

def get_db_connection():
    """ডাটাবেসের সাথে একটি নতুন কানেকশন তৈরি করে।"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def create_table():
    """বট চালু হওয়ার সময় এই ফাংশনটি ডাটাবেসে টেবিল তৈরি করবে (যদি না থাকে)।"""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS balances (
                    user_id BIGINT PRIMARY KEY,
                    hold FLOAT DEFAULT 0.0,
                    main FLOAT DEFAULT 0.0,
                    last_hold_update TIMESTAMP
                );
                """)
                conn.commit()
            print("Table 'balances' checked/created successfully.")
        except Exception as e:
            print(f"Error creating table: {e}")
        finally:
            conn.close()

def load_balances():
    """ডাটাবেস থেকে সব ইউজারের ব্যালেন্স লোড করে।"""
    conn = get_db_connection()
    balances = {}
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id, hold, main, last_hold_update FROM balances")
                rows = cur.fetchall()
                for row in rows:
                    user_id, hold, main, last_hold_update = row
                    balances[user_id] = {
                        'hold': hold,
                        'main': main,
                        'last_hold_update': last_hold_update
                    }
            print(f"Loaded {len(balances)} users from database.")
        except Exception as e:
            print(f"Error loading balances: {e}")
        finally:
            conn.close()
    return balances

def save_balances(balances):
    """বটের মেমরিতে থাকা সব ব্যালেন্স ডাটাবেসে সেভ করে।"""
    if not balances:
        print("No balances to save.")
        return

    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                # 데이터를 (user_id, hold, main, last_hold_update) এই ফরম্যাটে রেডি করা
                data_to_save = []
                for user_id, data in balances.items():
                    data_to_save.append((
                        user_id,
                        data.get('hold', 0.0),
                        data.get('main', 0.0),
                        data.get('last_hold_update') # এটি None হতে পারে
                    ))

                # executemany ব্যবহার করে একবারে সব ডাটা আপডেট করা (অনেক ফাস্ট)
                sql_query = """
                INSERT INTO balances (user_id, hold, main, last_hold_update)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    hold = EXCLUDED.hold,
                    main = EXCLUDED.main,
                    last_hold_update = EXCLUDED.last_hold_update;
                """
                cur.executemany(sql_query, data_to_save)
                conn.commit()
            # print(f"Successfully saved {len(data_to_save)} users to database.")
        except Exception as e:
            print(f"Error saving balances: {e}")
        finally:
            conn.close()

# --- আপনার পুরোনো কোড (কিছুটা পরিবর্তনসহ) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # এখানে আমরা ADMIN_ID ভেরিয়েবল ব্যবহার করছি
    if update.effective_user.id == ADMIN_ID:
        keyboard = [
            ['👤 Userinfo', '🔄 Hold', '💰 Main'],
            ['📊 Stats', '💵 Mainusdt', '💎 hoblcon'],
            ['📢 Notification', '❓ Help'],
            ['🟢 On', '🔴 Off'],
            ['👨‍💼 Owner account']
        ]
    else:
        keyboard = [
            ['➕ Register a new Gmail', '💰 Balance'],
            ['💸 Balance Transfer', '👥 Referral'],
            ['📧 Old Gmail sell', '🛒 Buy Gmail'],
            ['👨‍💼 Owner account', '👥 Total User']
        ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Welcome! Choose an option below:", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # Always allow admin access
    # এখানেও ADMIN_ID ভেরিয়েবল ব্যবহার করছি
    if user_id != ADMIN_ID and not context.bot_data.get('bot_status', True):
        await update.message.reply_text("🔴 Bot is currently OFF! Payments are being processed for users. Our bot has reached a large number of users and will be offline for a few hours.")
        return

    if not context.bot_data.get("user_balances"):
        context.bot_data["user_balances"] = {}
        
    # নতুন ইউজারকে ডাটাবেসের ডিফল্ট ভ্যালু দিয়ে যোগ করা
    if user_id not in context.bot_data["user_balances"]:
        context.bot_data["user_balances"][user_id] = {
            'hold': 0, 
            'main': 0, 
            'last_hold_update': None # নতুন ফিল্ড
        }

    if text == '❓ Help':
        await update.message.reply_text("Need help? Contact our support team!")
    elif text == '💰 Balance':
        user_balances = context.bot_data["user_balances"][update.effective_user.id]
        hold_balance = user_balances['hold']
        main_balance = user_balances['main']
        keyboard = [['💸 Withdrawal'], ['🔙 Back to Main Menu']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        balance_text = f"💰 Your Balances:\n\n💰 Hold Balance: {hold_balance:.2f} USDT\n💰 Main Balance: {main_balance:.2f} USDT\n\n👤 Your Chat ID: <code>{update.effective_user.id}</code>"
        await update.message.reply_text(balance_text, reply_markup=reply_markup, parse_mode='HTML')
    
    # ... (বাকি সব কোড আগের মতোই থাকবে) ...
    # ... (আমি শুধু জরুরি অংশগুলো কপি করেছি) ...
    # ... (আপনার পাঠানো main.py ফাইলের বাকি কোড এখানে পেস্ট করুন) ...
    
    # আপনার handle_message ফাংশনের বাকি সব কোড এখানে কপি-পেস্ট করুন
    # যেমন: elif text == '💸 Withdrawal': থেকে শুরু করে 
    # elif text == '🔴 Off' and update.effective_user.id == ADMIN_ID: পর্যন্ত
    
    # --- আমি আপনার handle_message ফাংশনের বাকি কোড নিচে পেস্ট করছি ---

    elif text == '💸 Withdrawal':
        keyboard = [
            ['USDT', 'TON', 'ETH'],
            ['🔙 Back to Main Menu']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Select withdrawal currency:", reply_markup=reply_markup)
    elif text in ['USDT', 'TON', 'ETH']:
        context.user_data['withdrawal_currency'] = text
        address_type = {
            'USDT': 'USDT BEP20',
            'TON': 'TON',
            'ETH': 'ETH'
        }[text]
        keyboard = [['🔙 Back to Main Menu']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(f"Please enter your {address_type} address:", reply_markup=reply_markup)
        context.user_data['awaiting_address'] = True
    elif context.user_data.get('awaiting_address'):
        context.user_data['withdrawal_address'] = text
        context.user_data['awaiting_address'] = False
        context.user_data['awaiting_amount'] = True
        await update.message.reply_text("Please enter withdrawal amount:")
    elif context.user_data.get('awaiting_amount'):
        try:
            amount = float(text)
            if amount < 1:
                await update.message.reply_text("❌ Minimum withdrawal amount is 1 USDT\n\nJoin our withdrawal channel: https://t.me/+djhhtndhA1FjZWZl")
                context.user_data['awaiting_amount'] = False
                await start(update, context)
                return

            user_id = update.effective_user.id
            if context.bot_data["user_balances"][user_id]['main'] >= amount:
                processing_msg = await update.message.reply_text("💰 Processing withdrawal.")
                await asyncio.sleep(1)
                await processing_msg.edit_text("💰 Processing withdrawal..")
                await asyncio.sleep(1)
                await processing_msg.edit_text("💰 Processing withdrawal...")
                await asyncio.sleep(1)
                await processing_msg.edit_text("💰 Processing withdrawal....")
                await asyncio.sleep(1)
                await processing_msg.edit_text("💰 Processing withdrawal.....")
                await asyncio.sleep(1)

                # Deduct from main balance
                context.bot_data["user_balances"][user_id]['main'] -= amount

                await processing_msg.edit_text(f"✅ Withdrawal of {amount:.2f} USDT processed!\n\nYour funds will be transferred within 24-48 hours.\n\nNew Main Balance: {context.bot_data['user_balances'][user_id]['main']:.2f} USDT")
            else:
                await update.message.reply_text("❌ Insufficient balance for withdrawal")
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a valid number.")
        context.user_data['awaiting_amount'] = False
        await start(update, context)
    elif text == '👤 Userinfo' and update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("Please enter user's chat ID:")
        context.user_data['awaiting_user_info'] = True
    elif context.user_data.get('awaiting_user_info'):
        try:
            user_id = int(text)
            if not context.bot_data.get("user_balances"):
                context.bot_data["user_balances"] = {}

            user_balances = context.bot_data["user_balances"].get(user_id, {'hold': 0, 'main': 0})

            keyboard = [['Hol', 'Man']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            info_message = f"👤 User Info (ID: {user_id})\n\n"
            info_message += f"💰 Hold Balance: {user_balances['hold']:.2f} USDT\n"
            info_message += f"💰 Main Balance: {user_balances['main']:.2f} USDT"

            context.user_data['current_user_id'] = user_id
            await update.message.reply_text(info_message, reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("Invalid user ID. Please try again.")
        context.user_data['awaiting_user_info'] = False
    elif text == 'Hol' and update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("Enter amount:")
        context.user_data['awaiting_hold_amount'] = True
    elif context.user_data.get('awaiting_hold_amount'):
        try:
            amount = float(text)
            context.user_data['temp_amount'] = amount
            keyboard = [['Add', 'Rem'], ['Cancel']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(f"Amount: {amount:.2f} USDT\nChoose action:", reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("Invalid amount. Please enter a valid number.")
            context.user_data['awaiting_hold_amount'] = False
            await start(update, context)
    elif text in ['Add', 'Rem'] and 'temp_amount' in context.user_data:
        user_id = context.user_data.get('current_user_id')
        amount = context.user_data['temp_amount']

        if not context.bot_data.get("user_balances"):
            context.bot_data["user_balances"] = {}
        if user_id not in context.bot_data["user_balances"]:
            context.bot_data["user_balances"][user_id] = {
                'hold': 0,
                'main': 0,
                'last_hold_update': datetime.now()
            }

        last_update = context.bot_data["user_balances"][user_id].get('last_hold_update')
        # 24 ঘণ্টা চেক করার লজিক
        if last_update and isinstance(last_update, datetime) and (datetime.now() - last_update) > timedelta(hours=24):
            context.bot_data["user_balances"][user_id]['hold'] = 0

        if text == 'Add':
            context.bot_data["user_balances"][user_id]['hold'] += amount
            context.bot_data["user_balances"][user_id]['last_hold_update'] = datetime.now()
            await update.message.reply_text(f"✅ Added {amount:.2f} USDT\nNew Hold Balance: {context.bot_data['user_balances'][user_id]['hold']:.2f} USDT")
        else:  # Rem
            if context.bot_data["user_balances"][user_id]['hold'] >= amount:
                context.bot_data["user_balances"][user_id]['hold'] -= amount
                await update.message.reply_text(f"✅ Removed {amount:.2f} USDT\nNew Hold Balance: {context.bot_data['user_balances'][user_id]['hold']:.2f} USDT")
            else:
                await update.message.reply_text("❌ Insufficient balance")

        context.user_data.pop('temp_amount', None)
        await start(update, context)
    elif text in ['🔄 Hold', '💰 Main'] and update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("Please enter user's chat ID:")
        context.user_data['awaiting_user_id'] = True
        context.user_data['admin_action'] = text
    elif context.user_data.get('awaiting_user_id'):
        try:
            user_id = int(text)
            context.user_data['target_user_id'] = user_id
            keyboard = [['Hold balance', 'Main balance'], ['🔙 Back to Main Menu']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("Select balance type to modify:", reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("Invalid user ID. Please try again.")
        context.user_data['awaiting_user_id'] = False
    elif text in ['Hold balance', 'Main balance'] and update.effective_user.id == ADMIN_ID:
        context.user_data['selected_balance'] = text.lower().replace(' ', '_')
        await update.message.reply_text(f"Enter amount to add/subtract from {text} (use - for subtraction):")
        context.user_data['awaiting_balance_change'] = True
    elif context.user_data.get('awaiting_balance_change'):
        try:
            amount = float(text)
            user_id = context.user_data.get('target_user_id')
            balance_type_key = context.user_data.get('selected_balance')
            
            # 'hold_balance' বা 'main_balance' কে 'hold' বা 'main' এ রূপান্তর
            balance_type = 'hold' if 'hold' in balance_type_key else 'main'
            
            if user_id and balance_type:
                if not context.bot_data.get("user_balances"):
                    context.bot_data["user_balances"] = {}
                if user_id not in context.bot_data["user_balances"]:
                    context.bot_data["user_balances"][user_id] = {'hold': 0, 'main': 0, 'last_hold_update': None}
                
                context.bot_data["user_balances"][user_id][balance_type] += amount
                await update.message.reply_text(f"Balance updated successfully! New {balance_type}: {context.bot_data['user_balances'][user_id][balance_type]:.2f} USDT")
        except ValueError:
            await update.message.reply_text("Invalid amount. Please enter a valid number.")
        context.user_data['awaiting_balance_change'] = False
        await start(update, context)
    elif text == '👨‍💼 Owner account':
        await update.message.reply_text("Contact owner: https://t.me/+djhhtndhA1FjZWZl")
    elif text == '➕ Register a new Gmail':
        if context.user_data.get('registration_complete', False):
            context.user_data['registration_complete'] = False

        import random
        import string

        def generate_unique_name():
            first_names = ["Alexander", "Benjamin", "Christopher", "Daniel", "Edward", "Frederick", "Gregory",
                         "Harrison", "Isaac", "Jonathan", "Kenneth", "Lawrence", "Michael", "Nicholas",
                         "Oliver", "Patrick", "Quentin", "Richard", "Stephen", "Timothy"]
            last_names = ["Anderson", "Baker", "Carter", "Davis", "Evans", "Foster", "Graham",
                        "Harris", "Irving", "Johnson", "Kennedy", "Lewis", "Mitchell", "Nelson",
                        "Parker", "Quinn", "Roberts", "Smith", "Thompson", "Walker"]
            return random.choice(first_names), random.choice(last_names)

        def generate_unique_email():
            letters = string.ascii_lowercase
            email_user = ''.join(random.sample(letters, 16))
            return f"{email_user}@gmail.com"

        def generate_password():
            letters = ''.join(random.choices(string.ascii_lowercase, k=8))
            numbers = ''.join(random.choices(string.digits, k=3))
            return f"{letters}{numbers}"

        first_name, last_name = generate_unique_name()
        random_email = generate_unique_email()
        random_password = generate_password()

        email_user = random_email.split('@')[0]
        message = f"""Register a Gmail account using the specified data and get 0.14$ USDT

First name: {first_name}
Last name: {last_name}
Gmail address. 👉 <code>{email_user}</code>@gmail.com
Password👉 <code>{random_password}</code>

📌 Be sure to use the specified password, otherwise the account will not be paid"""

        keyboard = [
            [
                InlineKeyboardButton("✅ Done", callback_data="gmail_done"),
                InlineKeyboardButton("📢 Channel", url="https://t.me/+djhhtndhA1FjZWZl")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['last_gmail_data'] = message
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')
    elif text == 'Done': # এই বাটনটি ইনলাইন হওয়া উচিত, টেক্সট নয়। এটি button_callback এ আছে।
        admin_chat_id = ADMIN_ID
        try:
            last_registration = context.user_data.get('last_registration', 'No registration data')
            context.bot_data["user_balances"][user_id]['hold'] += 0.14

            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=f"New Gmail Registration:\n{message}\n\nFrom User: {update.effective_user.id}"
            )
            await update.message.reply_text("✅ Registration submitted successfully!\n\n💰 0.14 USDT added to your Hold Balance!")
        except Exception as e:
            await update.message.reply_text("Error submitting registration. Please try again.")
    elif text == 'Cancel':
        keyboard = [
            ['➕ Register a new Gmail', '💰 Balance'],
            ['💸 Balance Transfer', '👥 Referral'],
            ['📧 Old Gmail sell', '🛒 Buy Gmail'],
            ['👨‍💼 Owner account', '👥 Total User']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        # আপনার মূল কোডে 'reply_text' নামে একটি ভেরিয়েবল ছিল, ওটা 'reply_markup' হবে
        await update.message.reply_text("Operation cancelled. Main menu:", reply_markup=reply_markup)
    elif text == '👥 Referral':
        user_id = update.effective_user.id
        if not context.bot_data.get("referrals"):
            context.bot_data["referrals"] = {}

        referral_count = len(context.bot_data["referrals"].get(str(user_id), []))
        referral_link = f"https://t.me/{context.bot.username}?start={user_id}"

        referral_message = f"""🎉 Referral Program:

1️⃣ Per Referral: 0.01 USDT
5️⃣0️⃣ Referrals: Bonus 0.02 USDT!

👥 Your Total Referrals: {referral_count}

Your Referral Link:
<code>{referral_link}</code>

Share this link with your friends! 🚀"""
        keyboard = [
            [InlineKeyboardButton("Share Link", url=referral_link)],
            [InlineKeyboardButton("👥 My Referrals", callback_data="my_referrals")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(referral_message, reply_markup=reply_markup, parse_mode='HTML')
    elif text == '👥 Total User':
        total_users = context.bot_data.get('total_users', 0)
        await update.message.reply_text(f"📊 Total Users: {total_users:,}")
    elif text == '📊 Stats':
        if update.effective_user.id == ADMIN_ID:  # Admin check
            await update.message.reply_text("Please enter the number of total users to display:")
            context.user_data['awaiting_stats'] = True
    elif context.user_data.get('awaiting_stats'):
        try:
            amount = int(text)
            keyboard = [['Confirm', 'Cancel']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            context.user_data['stats_amount'] = amount
            await update.message.reply_text(f"Set total users to: {amount:,}\nPlease confirm:", reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("Invalid number. Please try again.")
        context.user_data['awaiting_stats'] = False
    elif text == 'Confirm' and 'stats_amount' in context.user_data:
        context.bot_data['total_users'] = context.user_data['stats_amount']
        await update.message.reply_text("✅ Total users count updated successfully!")
        await start(update, context)
    elif text == '💵 Mainusdt' and update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("Please enter user's chat ID:")
        context.user_data['awaiting_mainusdt_id'] = True
    elif context.user_data.get('awaiting_mainusdt_id'):
        try:
            user_id = int(text)
            context.user_data['mainusdt_user_id'] = user_id
            keyboard = [['Adte', 'Remove']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("Choose action:", reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("Invalid user ID. Please try again.")
            await start(update, context)
        context.user_data['awaiting_mainusdt_id'] = False
    elif text in ['Adte', 'Remove'] and 'mainusdt_user_id' in context.user_data:
        context.user_data['mainusdt_action'] = text
        await update.message.reply_text("Enter amount:")
        context.user_data['awaiting_mainusdt_amount'] = True
    elif context.user_data.get('awaiting_mainusdt_amount'):
        try:
            amount = float(text)
            user_id = context.user_data['mainusdt_user_id']
            action = context.user_data['mainusdt_action']

            if not context.bot_data.get("user_balances"):
                context.bot_data["user_balances"] = {}
            if user_id not in context.bot_data["user_balances"]:
                context.bot_data["user_balances"][user_id] = {'hold': 0, 'main': 0, 'last_hold_update': None}

            target_user_balances = context.bot_data["user_balances"][user_id]

            if action == 'Adte':
                target_user_balances['main'] += amount
                await update.message.reply_text(f"✅ Added {amount:.2f} USDT\nNew Main Balance: {target_user_balances['main']:.2f} USDT")

                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"💰 {amount:.2f} USDT has been added to your Main Balance\nNew Main Balance: {target_user_balances['main']:.2f} USDT"
                    )
                except:
                    pass
            else:  # Remove
                if target_user_balances['main'] >= amount:
                    target_user_balances['main'] -= amount
                    await update.message.reply_text(f"✅ Removed {amount:.2f} USDT\nNew Main Balance: {target_user_balances['main']:.2f} USDT")

                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"⚠️ {amount:.2f} USDT has been removed from your Main Balance\nNew Main Balance: {target_user_balances['main']:.2f} USDT"
                        )
                    except:
                        pass
                else:
                    await update.message.reply_text("❌ Insufficient balance")

            context.user_data.pop('mainusdt_user_id', None)
            context.user_data.pop('mainusdt_action', None)
            await start(update, context)
        except ValueError:
            await update.message.reply_text("Invalid amount. Please enter a valid number.")
            await start(update, context)
        context.user_data['awaiting_mainusdt_amount'] = False
    elif text == '📢 Notification' and update.effective_user.id == ADMIN_ID:
        keyboard = [
            ['Send to All Users'],
            ['Send to Specific User'],
            ['Cancel']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Choose notification type:", reply_markup=reply_markup)
    elif text == 'Send to All Users' and update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("Please enter your notification message:")
        context.user_data['awaiting_notification'] = True
        context.user_data['notification_type'] = 'all'
    elif text == 'Send to Specific User' and update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("Please enter user's chat ID:")
        context.user_data['awaiting_specific_user'] = True
    elif context.user_data.get('awaiting_specific_user'):
        try:
            user_id = int(text)
            context.user_data['specific_user_id'] = user_id
            await update.message.reply_text("Please enter your notification message:")
            context.user_data['awaiting_notification'] = True
            context.user_data['notification_type'] = 'specific'
            context.user_data['awaiting_specific_user'] = False
        except ValueError:
            await update.message.reply_text("Invalid user ID. Please try again.")
            await start(update, context)
    elif context.user_data.get('awaiting_notification'):
        notification_message = text
        keyboard = [['Confirm', 'Cancel']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        context.user_data['notification_message'] = notification_message
        preview = f"Your notification message:\n\n{notification_message}"
        if context.user_data.get('notification_type') == 'specific':
            preview += f"\n\nTo be sent to user: {context.user_data['specific_user_id']}"
        await update.message.reply_text(f"{preview}\n\nConfirm to send?", reply_markup=reply_markup)
        context.user_data['awaiting_notification'] = False
        context.user_data['confirming_notification'] = True
    elif context.user_data.get('confirming_notification'):
        notification_message = context.user_data.get('notification_message', '')
        sent_count = 0
        failed_count = 0

        if context.user_data.get('notification_type') == 'specific':
            user_id = context.user_data['specific_user_id']
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📢 Admin Notification:\n\n{notification_message}",
                    disable_notification=False
                )
                sent_count = 1
            except:
                failed_count += 1
                await update.message.reply_text(f"❌ Failed to send notification to user {user_id}")
        else:
            all_users = set()
            if context.bot_data.get("user_balances"):
                for user_id in context.bot_data["user_balances"].keys():
                    all_users.add(user_id)
            
            for user_id in all_users:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"📢 Admin Notification:\n\n{notification_message}",
                        disable_notification=False,
                        parse_mode='HTML'
                    )
                    sent_count += 1
                except Exception as e:
                    failed_count += 1
                    print(f"Failed to send notification to {user_id}: {str(e)}")
                    continue

        await update.message.reply_text(f"✅ Notification sent to {sent_count} users!")
        context.user_data.clear()
        await start(update, context)
    elif text == '💎 hoblcon' and update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("Please enter user's chat ID:")
        context.user_data['awaiting_hoblcon_id'] = True
    elif context.user_data.get('awaiting_hoblcon_id'):
        try:
            user_id = int(text)
            context.user_data['hoblcon_user_id'] = user_id
            keyboard = [['Adte', 'Remove']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("Choose action:", reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("Invalid user ID. Please try again.")
            await start(update, context)
        context.user_data['awaiting_hoblcon_id'] = False
    elif text in ['Adte', 'Remove'] and 'hoblcon_user_id' in context.user_data:
        context.user_data['hoblcon_action'] = text
        await update.message.reply_text("Enter amount:")
        context.user_data['awaiting_hoblcon_amount'] = True
    elif context.user_data.get('awaiting_hoblcon_amount'):
        try:
            amount = float(text)
            user_id = context.user_data['hoblcon_user_id']
            action = context.user_data['hoblcon_action']

            if not context.bot_data.get("user_balances"):
                context.bot_data["user_balances"] = {}
            if user_id not in context.bot_data["user_balances"]:
                context.bot_data["user_balances"][user_id] = {'hold': 0, 'main': 0, 'last_hold_update': None}

            target_user_balances = context.bot_data["user_balances"][user_id]

            if action == 'Adte':
                target_user_balances['hold'] += amount
                await update.message.reply_text(f"✅ Added {amount:.2f} USDT\nNew Hold Balance: {target_user_balances['hold']:.2f} USDT")

                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"💰 {amount:.2f} USDT has been added to your Hold Balance\nNew Hold Balance: {target_user_balances['hold']:.2f} USDT"
                    )
                except:
                    pass
            else:  # Remove
                if target_user_balances['hold'] >= amount:
                    target_user_balances['hold'] -= amount
                    await update.message.reply_text(f"✅ Removed {amount:.2f} USDT\nNew Hold Balance: {target_user_balances['hold']:.2f} USDT")

                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"⚠️ {amount:.2f} USDT has been removed from your Hold Balance\nNew Hold Balance: {target_user_balances['hold']:.2f} USDT"
                        )
                    except:
                        pass
                else:
                    await update.message.reply_text("❌ Insufficient balance")

            context.user_data.pop('hoblcon_user_id', None)
            context.user_data.pop('hoblcon_action', None)
            await start(update, context)
        except ValueError:
            await update.message.reply_text("Invalid amount. Please enter a valid number.")
            await start(update, context)
        context.user_data['awaiting_hoblcon_amount'] = False
    elif text == '📧 Old Gmail sell':
        intro_message = "📧 Sell Your Gmail Account\n\n💰 Price per Gmail: 0.14 USDT\n\nPlease enter your Gmail address:"
        await update.message.reply_text(intro_message)
        context.user_data['awaiting_gmail_address'] = True
    elif context.user_data.get('awaiting_gmail_address'):
        context.user_data['gmail_address'] = text
        context.user_data['awaiting_gmail_address'] = False
        context.user_data['awaiting_gmail_password'] = True
        await update.message.reply_text("Please enter your Gmail password:")
    elif context.user_data.get('awaiting_gmail_password'):
        gmail_address = context.user_data.get('gmail_address')
        gmail_password = text

        admin_message = f"""
New Gmail Sale Request:
User ID: {update.effective_user.id}
Gmail: {gmail_address}
Password: {gmail_password}
"""
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
        except:
            pass

        context.user_data.clear()
        await update.message.reply_text("✅ Your request has been submitted successfully! Your balance will be updated within 24 hours after admin review.")

    elif text == '🛒 Buy Gmail':
        buy_message = """🛒 Buy Gmail Accounts

Available accounts:
• Fresh Gmail - 0.25 USDT
• Aged Gmail (1yr+) - 0.80 USDT
• Aged Gmail (2yr+) - 1.50 USDT

Contact @Deploper_Gmail_Ofc_store to purchase"""
        await update.message.reply_text(buy_message)

    elif text == '🔙 Back to Main Menu':
        # অ্যাডমিন আইডি চেক করে সঠিক মেন্যু দেখানো
        if update.effective_user.id == ADMIN_ID:
            keyboard = [
                ['👤 Userinfo', '🔄 Hold', '💰 Main'],
                ['📊 Stats', '💵 Mainusdt', '💎 hoblcon'],
                ['📢 Notification', '❓ Help'],
                ['🟢 On', '🔴 Off'],
                ['👨‍💼 Owner account']
            ]
        else:
            keyboard = [
                ['➕ Register a new Gmail', '💰 Balance'],
                ['💸 Balance Transfer', '👥 Referral'],
                ['📧 Old Gmail sell', '🛒 Buy Gmail'],
                ['👨‍💼 Owner account', '👥 Total User']
            ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Back to main menu:", reply_markup=reply_markup)
    elif text == '💸 Balance Transfer':
        await update.message.reply_text("Enter recipient's chat ID:")
        context.user_data.clear()
        context.user_data['awaiting_transfer_recipient'] = True
    elif context.user_data.get('awaiting_transfer_recipient'):
        try:
            recipient_id = int(text)
            context.user_data['transfer_recipient'] = recipient_id
            context.user_data['awaiting_transfer_recipient'] = False
            await update.message.reply_text("Enter amount to transfer:")
            context.user_data['awaiting_transfer_amount'] = True
        except ValueError:
            await update.message.reply_text("Invalid ID. Please enter a valid number.")
            context.user_data['awaiting_transfer_recipient'] = False
            await start(update, context)
    elif context.user_data.get('awaiting_transfer_amount'):
        try:
            amount = float(text)
            if amount <= 0:
                await update.message.reply_text("Amount must be greater than 0.")
                return

            user_id = update.effective_user.id
            user_balances = context.bot_data["user_balances"].get(user_id, {'main': 0})
            main_balance = user_balances['main']

            if main_balance >= amount:
                recipient_id = context.user_data['transfer_recipient']
                keyboard = [['Confirm', 'Cancel']]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    f"Please confirm transfer:\nTo: {recipient_id}\nAmount: {amount:.2f} USDT",
                    reply_markup=reply_markup
                )
                context.user_data['transfer_amount'] = amount
                context.user_data['awaiting_confirmation'] = True
                context.user_data['awaiting_transfer_amount'] = False
            else:
                await update.message.reply_text("Insufficient balance.")
                await start(update, context)
        except ValueError:
            await update.message.reply_text("Invalid amount. Please enter a valid number.")
            await start(update, context)
    elif context.user_data.get('awaiting_confirmation'):
        if text == 'Confirm':
            processing_msg = await update.message.reply_text("Processing transfer...")

            await asyncio.sleep(5)

            user_id = update.effective_user.id
            recipient_id = context.user_data['transfer_recipient']
            amount = context.user_data['transfer_amount']

            user_balance = context.bot_data["user_balances"].get(user_id, {'main': 0})['main']

            await processing_msg.delete()

            if user_balance >= amount:
                if recipient_id not in context.bot_data["user_balances"]:
                    context.bot_data["user_balances"][recipient_id] = {'main': 0, 'hold': 0, 'last_hold_update': None}

                context.bot_data["user_balances"][user_id]['main'] -= amount
                context.bot_data["user_balances"][recipient_id]['main'] += amount

                await update.message.reply_text(f"Transfer successful! {amount:.2f} USDT sent to user {recipient_id}.")
            else:
                await update.message.reply_text("❌ Insufficient balance for transfer.")

            try:
                await context.bot.send_message(
                    chat_id=recipient_id,
                    text=f"💰 {amount:.2f} USDT has been transferred to your Main Balance from user {user_id}.\nNew Main Balance: {context.bot_data['user_balances'][recipient_id]['main']:.2f} USDT"
                )
            except:
                pass

            context.user_data.clear()
            await start(update, context)
        elif text == 'Cancel':
            context.user_data.clear()
            await update.message.reply_text("Transfer cancelled.")
            await start(update, context)
    elif text == '🟢 On' and update.effective_user.id == ADMIN_ID:
        context.bot_data['bot_status'] = True
        await update.message.reply_text("✅ Bot is now ON!\n\nAll users will receive a message that bot is now on.")
        all_users = set()
        if context.bot_data.get("user_balances"):
            for user_id in context.bot_data["user_balances"].keys():
                all_users.add(user_id)
        for user_id in all_users:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="✅ Bot is now ON! Open your Gmail accounts now."
                )
            except:
                pass
    elif text == '🔴 Off' and update.effective_user.id == ADMIN_ID:
        context.bot_data['bot_status'] = False
        await update.message.reply_text("🔴 Bot is now OFF!\n\nAll users will receive a message that the bot is now off.")

        all_users = set()
        if context.bot_data.get("user_balances"):
            for user_id in context.bot_data["user_balances"].keys():
                all_users.add(user_id)

        for user_id in all_users:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🔴 Bot is now OFF! Payments are being processed for users. Our bot has reached a large number of users and will be offline for a few hours."
                )
            except:
                pass

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id # বাটন যে টিপছে তার আইডি

    if query.data.startswith("confirm_gmail_"):
        if user_id == ADMIN_ID:  # Admin check
            target_user_id = int(query.data.split("_")[2]) # যার জিমেইল, তার আইডি
            if target_user_id in context.bot_data["user_balances"]:
                if context.bot_data["user_balances"][target_user_id]['hold'] >= 0.14:
                    context.bot_data["user_balances"][target_user_id]['hold'] -= 0.14
                    context.bot_data["user_balances"][target_user_id]['main'] += 0.14

                    await query.message.edit_text(f"✅ Confirmed! Moved 0.14 USDT from Hold to Main balance for user {target_user_id}")

                    try:
                        await context.bot.send_message(
                            chat_id=target_user_id,
                            text="✅ Your Gmail registration has been confirmed! 0.14 USDT has been moved from Hold to Main balance."
                        )
                    except:
                        pass
                else:
                    await query.message.edit_text(f"⚠️ User {target_user_id} has insufficient hold balance (less than 0.14).")
            else:
                await query.message.edit_text(f"❌ User {target_user_id} not found in balances.")

    elif query.data.startswith("not_registered_gmail_"):
        if user_id == ADMIN_ID:
            target_user_id = int(query.data.split("_")[3])
            if target_user_id in context.bot_data["user_balances"]:
                if context.bot_data["user_balances"][target_user_id]['hold'] >= 0.14:
                    context.bot_data["user_balances"][target_user_id]['hold'] -= 0.14

                    await query.message.edit_text(f"❌ Gmail not registered! Removed 0.14 USDT from Hold balance for user {target_user_id}")

                    try:
                        await context.bot.send_message(
                            chat_id=target_user_id,
                            text="❌ Your Gmail registration was not completed. The Hold balance has been adjusted."
                        )
                    except:
                        pass
                else:
                    await query.message.edit_text(f"⚠️ User {target_user_id} has insufficient hold balance (less than 0.14).")
            else:
                await query.message.edit_text(f"❌ User {target_user_id} not found in balances.")


    elif query.data.startswith("blocked_gmail_"):
        if user_id == ADMIN_ID:
            target_user_id = int(query.data.split("_")[2])
            if target_user_id in context.bot_data["user_balances"]:
                if context.bot_data["user_balances"][target_user_id]['hold'] >= 0.14:
                    context.bot_data["user_balances"][target_user_id]['hold'] -= 0.14

                    await query.message.edit_text(f"🚫 Gmail blocked! Removed 0.14 USDT from Hold balance for user {target_user_id}")

                    try:
                        await context.bot.send_message(
                            chat_id=target_user_id,
                            text="🚫 Your Gmail registration was blocked. The Hold balance has been adjusted."
                        )
                    except:
                        pass
                else:
                    await query.message.edit_text(f"⚠️ User {target_user_id} has insufficient hold balance (less than 0.14).")
            else:
                await query.message.edit_text(f"❌ User {target_user_id} not found in balances.")


    if query.data == "gmail_done":
        target_user_id = update.effective_user.id # যে ইউজার বাটন টিপেছে
        if not context.bot_data.get("user_balances"):
            context.bot_data["user_balances"] = {}
        if target_user_id not in context.bot_data["user_balances"]:
            context.bot_data["user_balances"][target_user_id] = {'hold': 0, 'main': 0, 'last_hold_update': None}

        context.bot_data["user_balances"][target_user_id]['hold'] += 0.14
        context.bot_data["user_balances"][target_user_id]['last_hold_update'] = datetime.now() # হোল্ড আপডেটের সময় সেভ

        admin_chat_id = ADMIN_ID
        gmail_data = context.user_data.get('last_gmail_data', 'No Gmail data')
        admin_message = f"""
New Gmail Registration:
User ID: <code>{target_user_id}</code>

Credentials (click to copy):
{gmail_data}

Select action for this Gmail registration:"""

        keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_gmail_{target_user_id}")],
            [InlineKeyboardButton("❌ Not Registered", callback_data=f"not_registered_gmail_{target_user_id}")],
            [InlineKeyboardButton("🚫 Gmail Blocked", callback_data=f"blocked_gmail_{target_user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=admin_chat_id,
            text=admin_message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

        keyboard = [
            ['➕ Register a new Gmail', '💰 Balance'],
            ['💸 Balance Transfer', '👥 Referral'],
            ['📧 Old Gmail sell', '🛒 Buy Gmail'],
            ['👨‍💼 Owner account', '👥 Total User']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        context.user_data['registration_complete'] = True

        await query.message.edit_reply_markup(reply_markup=None)

        await query.message.reply_text("✅ Your Gmail registration has been successful. The amount has been added to your Hold Balance. Your Main Balance will be updated within 24 hours.", reply_markup=reply_markup)

async def save_balances_periodically(app):
    """প্রতি ৩০ সেকেন্ড পর পর ডাটাবেসে সেভ করবে।"""
    while True:
        await asyncio.sleep(30)
        if app.bot_data.get("user_balances"):
            save_balances(app.bot_data["user_balances"])

# এই ফাংশনটি আর দরকার নেই, কারণ save_balances_periodically সব সেভ করবে
# def update_balances(app, user_id, balance_type, amount, operation='add'):
#     pass

async def main():
    # টোকেন ভ্যালিডেশন
    if not TOKEN:
        print("Error: TOKEN not found in environment variables!")
        return
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in environment variables!")
        return

    # --- নতুন: বট চালু হওয়ার সময় টেবিল তৈরি করা ---
    create_table()

    app = Application.builder().token(TOKEN).build()

    # --- নতুন: ডাটাবেস থেকে ব্যালেন্স লোড করা ---
    app.bot_data["user_balances"] = load_balances() or {}
    app.bot_data['bot_status'] = True
    
    # referrals এবং total_users এর জন্য পুরোনো ডাটা লোড (যদি থাকে)
    # ভবিষ্যতে এগুলোও ডাটাবেসে নেওয়া উচিত
    app.bot_data["referrals"] = {} 
    app.bot_data["total_users"] = 0 


    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot starting with Database support...")
    print("Bot token:", app.bot.token[:10] + "..." if app.bot.token else "No token found!")

    async with app:
        await app.start()
        await app.updater.start_polling()
        # --- নতুন: প্রতি ৩০ সেকেন্ডে সেভ করার টাস্ক চালু করা ---
        asyncio.create_task(save_balances_periodically(app))
        
        # এই অংশটি আপনার মূল কোডে ছিল না, এটি যোগ করলে ভালো
        # এটি বট বন্ধ হওয়ার সময় শেষবারের মতো সেভ করবে
        try:
            while True:
                await asyncio.sleep(3600) # ১ ঘণ্টা পর পর স্লিপ
        except (KeyboardInterrupt, SystemExit):
            print("Bot stopping... saving final balances...")
            if app.bot_data.get("user_balances"):
                save_balances(app.bot_data["user_balances"])
            print("Final balances saved.")
        finally:
            await app.updater.stop()
            await app.stop()


if __name__ == "__main__":
    asyncio.run(main())