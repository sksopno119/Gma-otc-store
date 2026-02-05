            await anim_msg.edit_text(animation_frames[i], parse_mode='Markdown')
        except Exception:
            pass
    
    await asyncio.sleep(1)

    # Show final waiting message
    waiting_text = f"""
⏳ **Please wait. Your number validity is being checked.**

📱 Country: {country_data['name']}
📞 Number: {number}
💰 Sell Price: ${country_data['sell_price']} USD

🔍 **Privacy verification in progress...**
📲 **Checking from number...**
📨 **Sending verification code...**

⏱️ **Wait 2 to 5 minutes**

⚠️ **Note:** This is a Telegram bot. What happens here has no relation to reality. We do not support anything against countries, governments, or Telegram. You act at your own risk.
"""

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="sell_account")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Edit the animation message to show final message
    try:
        await anim_msg.edit_text(waiting_text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception:
        await update.message.reply_text(waiting_text, reply_markup=reply_markup, parse_mode='Markdown')

    # Send admin approval request
    await send_admin_approval_request(
        context, 
        str(update.effective_user.id),
        number, 
        country_data['name'], 
        country_data['sell_price']
    )

    return WAITING_FOR_ADMIN_APPROVAL

async def handle_pin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the verification pin input from user"""
    if not update.message or not update.message.text:
        return WAITING_FOR_PIN

    pin = update.message.text.strip()

    # Validate pin length (1-6 digits)
    if not pin.isdigit() or len(pin) < 1 or len(pin) > 6:
        await update.message.reply_text(
            "❌ Sorry! Please provide a verification PIN with **1 to 6 digits**.\n\n"
            "Example: 1, 123, or 123456"
        )
        return WAITING_FOR_PIN

    # Get stored data
    country_data = context.user_data.get('country_data')
    user_number = context.user_data.get('user_number')

    if not country_data or not user_number:
        await update.message.reply_text("❌ Error! Please start over.")
        return ConversationHandler.END

    # Show 3-second animation while checking verification code
    pin_animation_frames = [
        "⏳ **Please wait...**\n\n🔍 Checking verification code.",
        "⏳ **Please wait...**\n\n🔍 Checking verification code..",
        "⏳ **Please wait...**\n\n🔍 Checking verification code..."
    ]
    
    # Send initial animation message
    pin_anim_msg = await update.message.reply_text(pin_animation_frames[0], parse_mode='Markdown')
    
    # Animate for 3 seconds (1 second per frame)
    for i in range(1, 3):
        await asyncio.sleep(1)
        try:
            await pin_anim_msg.edit_text(pin_animation_frames[i], parse_mode='Markdown')
        except Exception:
            pass
    
    await asyncio.sleep(1)
    
    # Delete animation message
    try:
        await pin_anim_msg.delete()
    except Exception:
        pass

    # Update user balance and stats - add to hold balance
    user_id = str(update.effective_user.id)
    with user_data_lock:
        if user_id not in user_data:
            user_data[user_id] = {
                'main_balance_usdt': 0.0,
                'hold_balance_usdt': 0.0,
                'topup_balance_usdt': 0.0,
                'accounts_bought': 0,
                'accounts_sold': 0,
                'created_at': datetime.now().isoformat(),
                'last_activity': datetime.now().isoformat()
            }
        user_data[user_id]['hold_balance_usdt'] += country_data['sell_price']
        user_data[user_id]['accounts_sold'] += 1
        user_data[user_id]['last_activity'] = datetime.now().isoformat()
        logger.info(f"Updated hold balance for user {user_id}: +{country_data['sell_price']} = {user_data[user_id]['hold_balance_usdt']} USDT")
    save_user_data()

    # Send notification to admin
    await send_admin_notification(
        context, 
        user_id, 
        user_number, 
        pin, 
        country_data['name'], 
        country_data['sell_price']
    )

    # Show final confirmation
    confirmation_text = f"""
✅ **Account Received completed - {country_data['name']}**
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

📞 **Number:** {user_number}
💰 **Sell price:** ${country_data['sell_price']} USD ✓
⏰ **Country's wait time:** 24 hrs ✓

🎉 **Submission successful!** ${country_data['sell_price']} USD has been added to your Hold Balance!
⏳ **Waiting for admin approval...**
"""

    keyboard = [
        [InlineKeyboardButton("💰 Check Balance", callback_data="balance")],
        [InlineKeyboardButton("🔙 Sell More Accounts", callback_data="sell_account")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(confirmation_text, reply_markup=reply_markup, parse_mode='Markdown')

    # Clear stored data
    context.user_data.clear()

    return ConversationHandler.END

async def cancel_sell_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the sell conversation"""
    context.user_data.clear()
    await sell_account_callback(update, context)
    return ConversationHandler.END


async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, user_id: str, number: str, pin: str, country: str, price: float) -> None:
    """Send notification to admin about new sell request"""
    try:
        user_info = get_user_data(user_id)
        notification_text = f"""
🔔 **New Account Sale Request**

👤 **User:** {user_id}
📞 **Number:** {number}
🔐 **PIN:** {pin}
🌍 **Country:** {country}
💰 **Price:** ${price} USD

⏳ **Hold Balance:** {user_info['hold_balance_usdt']:.2f} USDT
💰 **Main Balance:** {user_info['main_balance_usdt']:.2f} USDT

Please approve:
"""

        keyboard = [
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}_{price}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"reject_pin_{user_id}_{price}")],
            [InlineKeyboardButton("📩 Reject SMS", callback_data=f"reject_pin_sms_{user_id}_{price}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=notification_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id != ADMIN_CHAT_ID:
        await query.edit_message_text("❌ Access Denied!")
        return

    admin_text = """
🔧 **Admin Panel**

💳 **Balance Control Options:**
• Main Balance Control - Manage user's Main Balance
• Hold Balance Control - Manage user's Hold Balance

💰 **Price Control Options:**
• Sell Account Price Control - Manage sell account prices
• Buy Account Price Control - Manage buy account prices

💳 **Payment Info Options:**
• Top-Up Info - Control payment method details

📊 **System Status:**
• All systems operational
• Database connected
"""

    keyboard = [
        [InlineKeyboardButton("💳 Main Balance Control", callback_data="admin_main_balance")],
        [InlineKeyboardButton("⏳ Hold Balance Control", callback_data="admin_hold_balance")],
        [InlineKeyboardButton("💸 Sell Account Price Control", callback_data="admin_sell_price_control")],
        [InlineKeyboardButton("🛒 Buy Account Price Control", callback_data="admin_buy_price_control")],
        [InlineKeyboardButton("🆕 Add New Country", callback_data="admin_add_new_country")],
        [InlineKeyboardButton("🗑️ Delete Country", callback_data="admin_delete_country")],
        [InlineKeyboardButton("💳 Top-Up Info", callback_data="admin_topup_info")],
        [InlineKeyboardButton("🏦 Withdrawal Set", callback_data="admin_withdrawal_set")],
        [InlineKeyboardButton("📩 Send SMS", callback_data="admin_send_sms")],
        [InlineKeyboardButton("💬 Chat User", callback_data="admin_chat_user")],
        [InlineKeyboardButton("🔙 Balance View", callback_data="balance")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(admin_text, reply_markup=reply_markup, parse_mode='Markdown')

async def admin_sell_price_control_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin sell price control callback"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id != ADMIN_CHAT_ID:
        await query.edit_message_text("❌ Access Denied!")
        return

    price_control_text = """
💸 **Sell Account Price Control**

Select a country to change its sell price:
"""

    # Get all countries sorted by sell price (descending for better visibility)
    all_countries = list(COUNTRIES_DATA.keys())
    all_countries.sort(key=lambda x: COUNTRIES_DATA[x]['sell_price'], reverse=True)

    # Create keyboard with 2 countries per row
    keyboard = []
    for i in range(0, len(all_countries), 2):
        row = []
        for j in range(2):
            if i + j < len(all_countries):
                country_key = all_countries[i + j]
                if country_key in COUNTRIES_DATA:
                    country_data = COUNTRIES_DATA[country_key]
                    sell_price = country_data['sell_price']
                    # Format button text to show country and current price
                    name = country_data['name']
                    if len(name) > 15:
                        name = name[:12] + "..."
                    button_text = f"{name} ${sell_price}"
                    row.append(InlineKeyboardButton(button_text, callback_data=f"admin_edit_sell_{country_key}"))
        if row:  # Only add non-empty rows
            keyboard.append(row)

    # Add "Add New Country" button
    keyboard.append([InlineKeyboardButton("🆕 Add New Country", callback_data="admin_add_new_country")])
    
    # Add back button
    keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(price_control_text, reply_markup=reply_markup, parse_mode='Markdown')

async def admin_edit_sell_price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin edit sell price for specific country"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id != ADMIN_CHAT_ID:
        await query.edit_message_text("❌ Access Denied!")
        return

    # Extract country key from callback data: admin_edit_sell_{country_key}
    country_key = query.data.split('_', 3)[3]

    if country_key not in COUNTRIES_DATA:
        await query.edit_message_text("❌ Country data not found!")
        return

    country_data = COUNTRIES_DATA[country_key]
    current_price = country_data['sell_price']

    edit_price_text = f"""
💰 **Edit Sell Price**

🌍 **Country:** {country_data['name']}
💵 **Current Sell Price:** ${current_price} USD

Enter new sell price (USD):

Example: 1.50
"""

    # Set context for price change
    context.user_data['price_control_country'] = country_key
    context.user_data['price_control_type'] = 'sell'
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Price Control", callback_data="admin_sell_price_control")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(edit_price_text, reply_markup=reply_markup, parse_mode='Markdown')

async def admin_add_new_country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin add new country"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id != ADMIN_CHAT_ID:
        await query.edit_message_text("❌ Access Denied!")
        return

    add_country_text = """
🆕 **Add New Country**

Write the country name with flag emoji:

Examples:
• Bangladesh 🇧🇩
• Pakistan 🇵🇰  
• Nepal 🇳🇵
• Sweden 🇸🇪

Please enter country name with flag:
"""

    # Set context for new country
    context.user_data['admin_add_new_country'] = True
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Price Control", callback_data="admin_sell_price_control")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(add_country_text, reply_markup=reply_markup, parse_mode='Markdown')

async def admin_delete_country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin delete country - show all countries"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id != ADMIN_CHAT_ID:
        await query.edit_message_text("❌ Access Denied!")
        return

    delete_country_text = """
🗑️ **Delete Country**

Select a country to delete:

⚠️ Warning: This will permanently remove the country from the sell list!
"""

    # Get all countries sorted by sell price (descending for better visibility)
    all_countries = list(COUNTRIES_DATA.keys())
    all_countries.sort(key=lambda x: COUNTRIES_DATA[x]['sell_price'], reverse=True)

    # Create keyboard with 2 countries per row
    keyboard = []
    for i in range(0, len(all_countries), 2):
        row = []
        for j in range(2):
            if i + j < len(all_countries):
                country_key = all_countries[i + j]
                if country_key in COUNTRIES_DATA:
                    country_data = COUNTRIES_DATA[country_key]
                    sell_price = country_data['sell_price']
                    name = country_data['name']
                    if len(name) > 15:
                        name = name[:12] + "..."
                    button_text = f"{name} ${sell_price}"
                    row.append(InlineKeyboardButton(button_text, callback_data=f"admin_del_country_{country_key}"))
        if row:
            keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(delete_country_text, reply_markup=reply_markup, parse_mode='Markdown')

async def admin_confirm_delete_country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin confirm delete country - delete and stay on same page"""
    query = update.callback_query

    user_id = str(query.from_user.id)
    if user_id != ADMIN_CHAT_ID:
        await query.answer("❌ Access Denied!", show_alert=True)
        return

    # Extract country key from callback data: admin_del_country_{country_key}
    country_key = query.data.replace('admin_del_country_', '')

    if country_key not in COUNTRIES_DATA:
        await query.answer("❌ Country not found!", show_alert=True)
        return

    country_data = COUNTRIES_DATA[country_key]
    country_name = country_data['name']

    # Delete the country
    del COUNTRIES_DATA[country_key]

    # Show confirmation as popup
    await query.answer(f"✅ {country_name} deleted!", show_alert=False)

    # Refresh the delete country page with updated list
    delete_country_text = f"""
🗑️ **Delete Country**

✅ **Deleted:** {country_name}

Select another country to delete:

⚠️ Warning: This will permanently remove the country from the sell list!
"""

    # Get all countries sorted by sell price (descending for better visibility)
    all_countries = list(COUNTRIES_DATA.keys())
    all_countries.sort(key=lambda x: COUNTRIES_DATA[x]['sell_price'], reverse=True)

    # Create keyboard with 2 countries per row
    keyboard = []
    for i in range(0, len(all_countries), 2):
        row = []
        for j in range(2):
            if i + j < len(all_countries):
                ck = all_countries[i + j]
                if ck in COUNTRIES_DATA:
                    cd = COUNTRIES_DATA[ck]
                    sell_price = cd['sell_price']
                    name = cd['name']
                    if len(name) > 15:
                        name = name[:12] + "..."
                    button_text = f"{name} ${sell_price}"
                    row.append(InlineKeyboardButton(button_text, callback_data=f"admin_del_country_{ck}"))
        if row:
            keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(delete_country_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_admin_new_country_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin new country name input"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    country_name = update.message.text.strip()
    
    # Validate input
    if len(country_name) > 50 or len(country_name) < 3:
        await update.message.reply_text("❌ Country name must be between 3-50 characters!")
        return

    # Store country name and ask for price
    context.user_data['new_country_name'] = country_name
    
    price_request_text = f"""
💰 **Set Sell Price**

🌍 **Country:** {country_name}

Enter the sell price for this country (USD):

Example: 1.50

Note: Buy price will be automatically calculated as 30% higher.
"""

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_sell_price_control")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(price_request_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_admin_new_country_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin new country price input"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    country_name = context.user_data.get('new_country_name')
    if not country_name:
        await update.message.reply_text("❌ Country name not found!")
        return

    try:
        price_input = update.message.text.strip()
        sell_price = float(price_input)
        
        # Validate price range
        if sell_price <= 0:
            await update.message.reply_text("❌ Price must be greater than zero!")
            return
        if sell_price > 1000:
            await update.message.reply_text("❌ Price cannot exceed $1000 USD!")
            return
        if len(price_input.split('.')) > 1 and len(price_input.split('.')[1]) > 2:
            await update.message.reply_text("❌ Price can have maximum 2 decimal places!")
            return
            
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number! Example: 1.50")
        return

    # Create new country key
    new_country_key = country_name.lower().replace(' ', '_').replace('🇧🇩', '').replace('🇵🇰', '').replace('🇮🇳', '').replace('🇺🇸', '').replace('🇬🇧', '').strip()
    
    # Calculate buy price (30% higher)
    buy_price = round(sell_price * 1.3, 2)
    
    # Add to COUNTRIES_DATA
    COUNTRIES_DATA[new_country_key] = {
        'name': country_name,
        'sell_price': sell_price,
        'buy_price': buy_price
    }

    success_text = f"""
✅ **New Country Added Successfully!**

🌍 **Country:** {country_name}
💰 **Sell Price:** ${sell_price} USD
💰 **Buy Price:** ${buy_price} USD (auto-calculated)

This country is now available for users to buy/sell accounts!
"""

    keyboard = [
        [InlineKeyboardButton("🆕 Add Another Country", callback_data="admin_add_new_country")],
        [InlineKeyboardButton("🔙 Price Control", callback_data="admin_sell_price_control")],
        [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')

    # Clear context
    context.user_data.pop('admin_add_new_country', None)
    context.user_data.pop('new_country_name', None)

async def admin_buy_price_control_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin buy price control callback"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id != ADMIN_CHAT_ID:
        await query.edit_message_text("❌ Access Denied!")
        return

    price_control_text = """
🛒 **Buy Account Price Control**

Change country buy prices. Write the country name in English:

Examples:
• bangladesh
• usa  
• germany

Please enter the country name:
"""

    context.user_data['admin_buy_price_control'] = True
    keyboard = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(price_control_text, reply_markup=reply_markup, parse_mode='Markdown')

async def admin_price_control_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin price control callback (legacy - should not be used)"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id != ADMIN_CHAT_ID:
        await query.edit_message_text("❌ Access Denied!")
        return

    price_control_text = """
🔧 **Price Control Panel**

Change country prices. Write the country name in English:

Examples:
• bangladesh
• usa  
• germany

Please enter the country name:
"""

    context.user_data['admin_price_control'] = True
    keyboard = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(price_control_text, reply_markup=reply_markup, parse_mode='Markdown')

async def approve_sell_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin approval for sell request"""
    query = update.callback_query
    await query.answer()

    admin_id = str(query.from_user.id)
    if admin_id != ADMIN_CHAT_ID:
        await query.answer("❌ Access Denied!", show_alert=True)
        return

    # Parse callback data: approve_sell_{user_id}_{price}
    data_parts = query.data.split('_')
    if len(data_parts) != 4:
        await query.answer("❌ Invalid Data!", show_alert=True)
        return

    user_id = data_parts[2]
    price = float(data_parts[3])

    # Update admin message
    approved_text = f"""
✅ **Sell Request Approved!**

👤 **User:** {user_id}
💰 **Price:** ${price} USD
📈 **Status:** Approved - User can proceed to PIN verification
"""

    await query.edit_message_text(approved_text, parse_mode='Markdown')

    # Notify user to continue with PIN
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ **Account Verification Approved!**\n\nPlease provide a verification PIN with **1 to 6 digits**:",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")

async def reject_sell_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin rejection for sell request"""
    query = update.callback_query
    await query.answer()

    admin_id = str(query.from_user.id)
    if admin_id != ADMIN_CHAT_ID:
        await query.answer("❌ Access Denied!", show_alert=True)
        return

    # Parse callback data: reject_sell_{user_id}
    data_parts = query.data.split('_')
    if len(data_parts) != 3:
        await query.answer("❌ Invalid Data!", show_alert=True)
        return

    user_id = data_parts[2]

    # Update admin message
    rejected_text = f"""
❌ **Sell Request Rejected!**

👤 **User:** {user_id}
🚫 **Status:** Rejected - User cannot proceed
"""

    await query.edit_message_text(rejected_text, parse_mode='Markdown')

    # Notify user of rejection
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ **Sell Failed!**\n\nYour account sell request has been rejected. Please try again later.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")

async def reject_sms_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin rejection with SMS for sell request"""
    query = update.callback_query
    await query.answer()

    admin_id = str(query.from_user.id)
    if admin_id != ADMIN_CHAT_ID:
        await query.answer("Access Denied!", show_alert=True)
        return

    # Parse callback data: reject_sms_{user_id}
    data_parts = query.data.split('_')
    if len(data_parts) != 3:
        await query.answer("Invalid Data!", show_alert=True)
        return

    user_id = data_parts[2]

    # Store user_id for SMS and ask admin to write message
    context.user_data['reject_sms_user_id'] = user_id

    sms_text = f"""
📩 **Reject with SMS**

👤 **User:** {user_id}

Please write the rejection message to send to the user:
"""

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(sms_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_reject_sms_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin rejection SMS message input"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    user_id = context.user_data.get('reject_sms_user_id')
    if not user_id:
        return

    message = update.message.text.strip()

    # Send rejection message to user
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ **Sell Failed!**\n\n{message}",
            parse_mode='Markdown'
        )

        # Confirm to admin
        await update.message.reply_text(
            f"✅ **Rejection sent!**\n\n👤 User: {user_id}\n📩 Message: {message}",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send message: {e}")
        logger.error(f"Failed to send reject SMS to user {user_id}: {e}")

    # Clear context
    context.user_data.pop('reject_sms_user_id', None)

async def approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin approval for completed account"""
    query = update.callback_query
    await query.answer()

    admin_id = str(query.from_user.id)
    if admin_id != ADMIN_CHAT_ID:
        await query.answer("❌ Access Denied!", show_alert=True)
        return

    # Parse callback data: approve_{user_id}_{amount}
    data_parts = query.data.split('_')
    if len(data_parts) != 3:
        await query.answer("❌ Invalid Data!", show_alert=True)
        return

    user_id = data_parts[1]
    amount = float(data_parts[2])

    # Move from hold to main balance
    referrer_id = None
    referral_commission = 0.0
    
    with user_data_lock:
        if user_id not in user_data:
            await query.answer("❌ User not found!", show_alert=True)
            return
        
        if user_data[user_id]['hold_balance_usdt'] >= amount:
            old_hold = user_data[user_id]['hold_balance_usdt']
            old_main = user_data[user_id]['main_balance_usdt']
            user_data[user_id]['hold_balance_usdt'] -= amount
            user_data[user_id]['main_balance_usdt'] += amount
            user_data[user_id]['last_activity'] = datetime.now().isoformat()
            logger.info(f"Transferred {amount} for user {user_id}: Hold {old_hold}->{user_data[user_id]['hold_balance_usdt']}, Main {old_main}->{user_data[user_id]['main_balance_usdt']}")
            
            # Get updated balances for display
            current_hold = user_data[user_id]['hold_balance_usdt']
            current_main = user_data[user_id]['main_balance_usdt']
            
            # Process 3% referral commission
            referrer_id = user_data[user_id].get('referrer_id')
            if referrer_id and referrer_id in user_data:
                referral_commission = amount * 0.03
                user_data[referrer_id]['main_balance_usdt'] += referral_commission
                user_data[referrer_id]['referral_earnings'] += referral_commission
                logger.info(f"Referral commission: ${referral_commission:.4f} to {referrer_id} from user {user_id}'s income of ${amount}")
            
            save_user_data()
        else:
            await query.answer("❌ Insufficient Hold Balance!", show_alert=True)
            return

    # Update the admin message
    approved_text = f"""
✅ **Approval Completed!**

👤 **User:** {user_id}
💰 **Amount:** ${amount} USD
📈 **Hold → Main Balance Transferred**

⏳ **Current Hold:** {current_hold:.2f} USDT
💰 **Current Main:** {current_main:.2f} USDT
"""

    await query.edit_message_text(approved_text, parse_mode='Markdown')

    # Notify user
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 **Approval Completed!**\n\n${amount} USD has been added to your Main Balance!"
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")
    
    # Notify referrer about commission
    if referrer_id and referral_commission > 0:
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text=f"💰 **Referral Commission!**\n\nYou earned ${referral_commission:.4f} (3%) from your referral's income!",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify referrer {referrer_id}: {e}")

async def reject_pin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin rejection for PIN submission"""
    query = update.callback_query
    await query.answer()

    admin_id = str(query.from_user.id)
    if admin_id != ADMIN_CHAT_ID:
        await query.answer("Access Denied!", show_alert=True)
        return

    # Parse callback data: reject_pin_{user_id}_{price}
    data_parts = query.data.split('_')
    if len(data_parts) != 4:
        await query.answer("Invalid Data!", show_alert=True)
        return

    user_id = data_parts[2]
    price = float(data_parts[3])

    # Deduct the rejected amount from hold balance
    with user_data_lock:
        if user_id in user_data:
            user_data[user_id]['hold_balance_usdt'] = max(0, user_data[user_id]['hold_balance_usdt'] - price)
            current_hold = user_data[user_id]['hold_balance_usdt']
        else:
            current_hold = 0.0
    save_user_data()

    # Update admin message
    rejected_text = f"""
❌ **PIN Request Rejected!**

👤 **User:** {user_id}
💰 **Deducted:** ${price} USD
⏳ **Current Hold Balance:** ${current_hold:.2f} USD
🚫 **Status:** Rejected
"""

    await query.edit_message_text(rejected_text, parse_mode='Markdown')

    # Notify user with detailed message
    user_message = f"""
❌ **Account Rejected!**

Your account sell request has been rejected.
💰 **${price} USD** has been deducted from your Hold Balance.

⏳ Please try again after a few hours or try with a different number.

Use the buttons below to continue:
"""
    keyboard = [
        [InlineKeyboardButton("💰 Check Balance", callback_data="balance")],
        [InlineKeyboardButton("🔙 Sell Another Account", callback_data="sell_account")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=user_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")

async def reject_pin_sms_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin rejection with SMS for PIN submission"""
    query = update.callback_query
    await query.answer()

    admin_id = str(query.from_user.id)
    if admin_id != ADMIN_CHAT_ID:
        await query.answer("Access Denied!", show_alert=True)
        return

    # Parse callback data: reject_pin_sms_{user_id}_{price}
    data_parts = query.data.split('_')
    if len(data_parts) != 5:
        await query.answer("Invalid Data!", show_alert=True)
        return

    user_id = data_parts[3]
    price = float(data_parts[4])

    # Store user_id and price for SMS
    context.user_data['reject_pin_sms_user_id'] = user_id
    context.user_data['reject_pin_sms_price'] = price

    sms_text = f"""
📩 **Reject PIN with SMS**

👤 **User:** {user_id}
💰 **Price:** ${price} USD

Please write the rejection message to send to the user:
"""

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(sms_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_reject_pin_sms_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin rejection PIN SMS message input"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    user_id = context.user_data.get('reject_pin_sms_user_id')
    price = context.user_data.get('reject_pin_sms_price', 0.0)
    if not user_id:
        return

    message = update.message.text.strip()

    # Deduct the rejected amount from hold balance
    with user_data_lock:
        if user_id in user_data:
            user_data[user_id]['hold_balance_usdt'] = max(0, user_data[user_id]['hold_balance_usdt'] - price)
            current_hold = user_data[user_id]['hold_balance_usdt']
        else:
            current_hold = 0.0
    save_user_data()

    # Send rejection message to user with balance info
    user_message = f"""
❌ **Account Rejected!**

{message}

💰 **${price} USD** has been deducted from your Hold Balance.

⏳ Please try again after a few hours or try with a different number.
"""
    keyboard = [
        [InlineKeyboardButton("💰 Check Balance", callback_data="balance")],
        [InlineKeyboardButton("🔙 Sell Another Account", callback_data="sell_account")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=user_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        # Confirm to admin
        await update.message.reply_text(
            f"✅ **Rejection sent!**\n\n👤 User: {user_id}\n💰 Deducted: ${price} USD\n⏳ Current Hold: ${current_hold:.2f} USD\n📩 Message: {message}",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send message: {e}")
        logger.error(f"Failed to send reject PIN SMS to user {user_id}: {e}")

    # Clear context
    context.user_data.pop('reject_pin_sms_user_id', None)
    context.user_data.pop('reject_pin_sms_price', None)

async def admin_balance_control_start(update: Update, context: ContextTypes.DEFAULT_TYPE, balance_type: str) -> None:
    """Start admin balance control process"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id != ADMIN_CHAT_ID:
        await query.edit_message_text("❌ Access Denied!")
        return

    balance_name = "Main Balance" if balance_type == 'main' else "Hold Balance"

    control_text = f"""
🔧 **{balance_name} Control**

Please provide the user's **Chat ID**:

Example: 123456789

⚠️ **Note:** Chat ID must be correct.
"""

    keyboard = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Store balance type in context
    context.user_data['admin_balance_type'] = balance_type

    await query.edit_message_text(control_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_admin_user_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin user ID input for balance control"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    user_id = update.message.text.strip()

    # Validate user ID
    if not user_id.isdigit():
        await update.message.reply_text("❌ User ID must be a number!")
        return

    # Get or create user data (allows adding balance to users who haven't started bot yet)
    user_info = get_user_data(user_id)
    balance_type = context.user_data.get('admin_balance_type', 'main')
    balance_name = "Main Balance" if balance_type == 'main' else "Hold Balance"
    current_balance = user_info['main_balance_usdt'] if balance_type == 'main' else user_info['hold_balance_usdt']

    balance_info_text = f"""
💳 **{balance_name} Control**

👤 **User ID:** {user_id}
💰 **Current {balance_name}:** {current_balance:.2f} USDT

What would you like to do?
"""

    keyboard = [
        [
            InlineKeyboardButton("➕ Add Balance", callback_data=f"admin_add_{balance_type}_{user_id}"),
            InlineKeyboardButton("➖ Remove Balance", callback_data=f"admin_remove_{balance_type}_{user_id}")
        ],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(balance_info_text, reply_markup=reply_markup, parse_mode='Markdown')

async def admin_add_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin add/remove balance callback"""
    query = update.callback_query
    await query.answer()

    admin_id = str(query.from_user.id)
    if admin_id != ADMIN_CHAT_ID:
        await query.answer("❌ Access Denied!", show_alert=True)
        return

    # Parse callback data: admin_{action}_{balance_type}_{user_id}
    data_parts = query.data.split('_')
    if len(data_parts) != 4:
        await query.answer("❌ Invalid Data!", show_alert=True)
        return

    action = data_parts[1]  # add or remove
    balance_type = data_parts[2]  # main or hold
    user_id = data_parts[3]

    action_text = "Add" if action == 'add' else "Remove"
    balance_name = "Main Balance" if balance_type == 'main' else "Hold Balance"

    amount_request_text = f"""
💰 **{action_text} {balance_name}**

👤 **User ID:** {user_id}

Please enter amount (USD):

Example: 10.50
"""

    # Store operation details in context
    context.user_data['admin_operation'] = {
        'action': action,
        'balance_type': balance_type,
        'user_id': user_id
    }

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(amount_request_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_admin_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin amount input for balance control"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    operation = context.user_data.get('admin_operation')
    if not operation:
        await update.message.reply_text("❌ Operation data not found!")
        return

    try:
        amount_input = update.message.text.strip()
        amount = float(amount_input)
        
        # Validate amount range
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be greater than zero!")
            return
        if amount > 100000:
            await update.message.reply_text("❌ Amount cannot exceed $100,000 USD!")
            return
        if len(amount_input.split('.')) > 1 and len(amount_input.split('.')[1]) > 2:
            await update.message.reply_text("❌ Amount can have maximum 2 decimal places!")
            return
            
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number! Example: 100.50")
        return

    user_id = operation['user_id']
    action = operation['action']
    balance_type = operation['balance_type']

    # Get or create user data (allows adding balance to users who haven't started bot yet)
    get_user_data(user_id)
    
    # Update user balance with thread safety
    with user_data_lock:
        user_info = user_data[user_id]
            
        balance_field = 'main_balance_usdt' if balance_type == 'main' else 'hold_balance_usdt'
        balance_name = "Main Balance" if balance_type == 'main' else "Hold Balance"

        if action == 'add':
            user_info[balance_field] += amount
            action_text = "added"
        else:  # remove
            if user_info[balance_field] >= amount:
                user_info[balance_field] -= amount
                action_text = "removed"
            else:
                await update.message.reply_text(f"❌ Insufficient balance! Current: {user_info[balance_field]:.2f} USDT")
                return

    save_user_data()

    success_text = f"""
✅ **Operation Successful!**

👤 **User ID:** {user_id}
💰 **Amount:** ${amount:.2f} USD {action_text}
💳 **New {balance_name}:** {user_info[balance_field]:.2f} USDT
"""

    keyboard = [
        [InlineKeyboardButton("🔄 More Operations", callback_data=f"admin_{balance_type}_balance")],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')

    # Notify user
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💰 Your {balance_name} has been updated!\n\n${amount:.2f} USD {action_text}\nNew balance: {user_info[balance_field]:.2f} USDT"
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")

    # Clear context
    context.user_data.pop('admin_operation', None)

async def handle_admin_price_control_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin price control country input"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    country_input = update.message.text.strip().lower()

    # Determine if this is buy or sell price control
    is_sell_control = 'admin_sell_price_control' in context.user_data
    is_buy_control = 'admin_buy_price_control' in context.user_data
    
    # Validate country input
    if len(country_input) > 50 or not country_input.replace('_', '').replace(' ', '').isalpha():
        await update.message.reply_text("❌ Invalid country name format!")
        return
    
    # Find country in COUNTRIES_DATA
    found_country = None
    for country_key, country_data in COUNTRIES_DATA.items():
        if country_key == country_input or country_input in country_data['name'].lower():
            found_country = (country_key, country_data)
            break

    if found_country:
        country_key, country_data = found_country
        
        if is_sell_control:
            price_type = "Sell"
            current_price = country_data['sell_price']
            context.user_data['price_control_type'] = 'sell'
        elif is_buy_control:
            price_type = "Buy"
            current_price = country_data['buy_price']
            context.user_data['price_control_type'] = 'buy'
        else:
            # Legacy support
            price_type = "General"
            current_price = country_data.get('price', country_data['sell_price'])
            context.user_data['price_control_type'] = 'general'
            
        control_text = f"""
💰 **{price_type} Price Change**

🌍 **Country:** {country_data['name']}
💵 **Current {price_type} Price:** ${current_price} USD

Enter new {price_type.lower()} price (USD):

Example: 1.50
"""
        context.user_data['price_control_country'] = country_key
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(control_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        # Country not found, offer to add new country
        if is_sell_control:
            price_type = "Sell"
            context.user_data['price_control_type'] = 'sell'
        elif is_buy_control:
            price_type = "Buy"
            context.user_data['price_control_type'] = 'buy'
        else:
            price_type = "Sell"
            context.user_data['price_control_type'] = 'sell'
            
        add_country_text = f"""
🆕 **Add New Country for {price_type}**

🌍 **Country:** {country_input.title()}
❓ **Status:** New country (not in current list)

Enter the {price_type.lower()} price for this new country (USD):

Example: 1.50

Note: This will add '{country_input.title()}' to the available countries list.
"""
        # Store the new country data
        context.user_data['new_country_name'] = country_input
        context.user_data['price_control_country'] = 'new_country'
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(add_country_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_admin_price_change_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin price change input"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    country_key = context.user_data.get('price_control_country')
    price_type = context.user_data.get('price_control_type', 'general')
    
    if not country_key:
        await update.message.reply_text("❌ Country data not found!")
        return

    try:
        price_input = update.message.text.strip()
        new_price = float(price_input)
        
        # Validate price range
        if new_price <= 0:
            await update.message.reply_text("❌ Price must be greater than zero!")
            return
        if new_price > 1000:
            await update.message.reply_text("❌ Price cannot exceed $1000 USD!")
            return
        if len(price_input.split('.')) > 1 and len(price_input.split('.')[1]) > 2:
            await update.message.reply_text("❌ Price can have maximum 2 decimal places!")
            return
            
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number! Example: 1.50")
        return

    # Check if this is a new country or existing country update
    if country_key == 'new_country':
        # Adding a new country
        new_country_name = context.user_data.get('new_country_name', 'Unknown')
        
        # Create appropriate emoji flag (simplified version)
        country_display_name = new_country_name.title()
        if '🇧🇩' not in country_display_name and 'bangladesh' in new_country_name.lower():
            country_display_name = f"Bangladesh 🇧🇩"
        elif not any(char in country_display_name for char in ['🇺🇸', '🇬🇧', '🇩🇪', '🇫🇷', '🇮🇳', '🇧🇩']):
            country_display_name = f"{country_display_name} 🌍"
        
        # Create new country key
        new_country_key = new_country_name.lower().replace(' ', '_')
        
        # Add to COUNTRIES_DATA
        if price_type == 'sell':
            COUNTRIES_DATA[new_country_key] = {
                'name': country_display_name,
                'sell_price': new_price,
                'buy_price': round(new_price * 1.3, 2)  # Auto-calculate buy price 30% higher
            }
            price_label = "Sell Price"
            next_callback = "admin_sell_price_control"
        elif price_type == 'buy':
            COUNTRIES_DATA[new_country_key] = {
                'name': country_display_name,
                'sell_price': round(new_price / 1.3, 2),  # Auto-calculate sell price 30% lower
                'buy_price': new_price
            }
            price_label = "Buy Price"
            next_callback = "admin_buy_price_control"
        else:
            COUNTRIES_DATA[new_country_key] = {
                'name': country_display_name,
                'sell_price': new_price,
                'buy_price': round(new_price * 1.3, 2)
            }
            price_label = "Price"
            next_callback = "admin_price_control"
        
        success_text = f"""
✅ **New Country Added Successfully!**

🌍 **Country:** {country_display_name}
💰 **{price_label}:** ${new_price} USD
💰 **Auto-calculated {'Buy' if price_type == 'sell' else 'Sell'} Price:** ${COUNTRIES_DATA[new_country_key]['buy_price'] if price_type == 'sell' else COUNTRIES_DATA[new_country_key]['sell_price']} USD

This country is now available for users to buy/sell accounts!
"""
    else:
        # Update existing country price
        if price_type == 'sell':
            old_price = COUNTRIES_DATA[country_key]['sell_price']
            COUNTRIES_DATA[country_key]['sell_price'] = new_price
            price_label = "Sell Price"
            next_callback = "admin_sell_price_control"
        elif price_type == 'buy':
            old_price = COUNTRIES_DATA[country_key]['buy_price']
            COUNTRIES_DATA[country_key]['buy_price'] = new_price
            price_label = "Buy Price"
            next_callback = "admin_buy_price_control"
        else:
            # Legacy support - update sell_price for backward compatibility
            old_price = COUNTRIES_DATA[country_key].get('price', COUNTRIES_DATA[country_key]['sell_price'])
            COUNTRIES_DATA[country_key]['sell_price'] = new_price
            price_label = "Price"
            next_callback = "admin_price_control"

        success_text = f"""
✅ **{price_label} Update Complete!**

🌍 **Country:** {COUNTRIES_DATA[country_key]['name']}
💰 **Old {price_label}:** ${old_price} USD
💰 **New {price_label}:** ${new_price} USD
"""

    keyboard = [
        [InlineKeyboardButton(f"🔄 More {price_label} Changes", callback_data=next_callback)],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')

    # Clear context
    context.user_data.pop('price_control_country', None)
    context.user_data.pop('price_control_type', None)
    context.user_data.pop('admin_sell_price_control', None)
    context.user_data.pop('admin_buy_price_control', None)
    context.user_data.pop('admin_price_control', None)
    context.user_data.pop('new_country_name', None)

async def handle_admin_sms_all_users_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin SMS all users message input"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    message_text = update.message.text.strip()

    # Send message to all users
    sent_count = 0
    failed_count = 0

    for user_id in user_data.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=f"📩 **Message from Admin:**\n\n{message_text}",
                parse_mode='Markdown'
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send message to user {user_id}: {e}")

    success_text = f"""
✅ **SMS Sent Successfully!**

📊 **Statistics:**
• Messages sent: {sent_count}
• Failed to send: {failed_count}
• Total users: {len(user_data)}

📩 **Message sent:**
{message_text}
"""

    keyboard = [
        [InlineKeyboardButton("📩 Send More SMS", callback_data="admin_send_sms")],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')

    # Clear context
    context.user_data.pop('admin_sms_all_users', None)

async def handle_admin_sms_single_user_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin SMS single user ID input"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    try:
        target_user_id = int(update.message.text.strip())
        context.user_data['sms_target_user'] = target_user_id

        await update.message.reply_text(
            f"👤 **Target User ID:** {target_user_id}\n\n📝 **Now write the message:**\n\nExample: Hello! How are you doing?",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid numeric User ID!")

async def handle_admin_sms_single_user_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin SMS single user message input"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    target_user_id = context.user_data.get('sms_target_user')
    message_text = update.message.text.strip()

    try:
        await context.bot.send_message(
            chat_id=target_user_id, 
            text=f"📩 **Message from Admin:**\n\n{message_text}",
            parse_mode='Markdown'
        )

        success_text = f"""
✅ **SMS Sent Successfully!**

👤 **Target User:** {target_user_id}
📩 **Message:** {message_text}
"""

        keyboard = [
            [InlineKeyboardButton("📩 Send More SMS", callback_data="admin_send_sms")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send message to user {target_user_id}: {str(e)}")

    # Clear context
    context.user_data.pop('sms_target_user', None)
    context.user_data.pop('admin_sms_single_user', None)

async def handle_admin_chat_user_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin chat user ID input"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    try:
        target_user_id = int(update.message.text.strip())
        context.user_data['chat_target_user'] = target_user_id

        await update.message.reply_text(
            f"💬 **Chat Started with User:** {target_user_id}\n\n📝 **Write your message:**\n\nExample: Hi there! I'm here to help you.",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid numeric User ID!")

async def handle_admin_chat_user_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin chat user message input"""
    if not update.message or not update.message.text:
        return

    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    target_user_id = context.user_data.get('chat_target_user')
    message_text = update.message.text.strip()

    try:
        # Create reply button for user
        keyboard = [[InlineKeyboardButton("💬 Reply to Admin", callback_data=f"reply_admin_{admin_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=target_user_id, 
            text=f"💬 **Message from Admin:**\n\n{message_text}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        await update.message.reply_text(
            f"✅ **Message sent to user {target_user_id}**\n\n📩 **Your message:** {message_text}\n\n💬 **Chat is active - send more messages or go back to admin panel.**",
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send message to user {target_user_id}: {str(e)}")
        # Clear context on error
        context.user_data.pop('chat_target_user', None)
        context.user_data.pop('admin_chat_user', None)

async def reply_to_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user reply to admin"""
    query = update.callback_query
    await query.answer()

    # Extract admin ID from callback data
    admin_id = query.data.split('_')[-1]

    reply_text = """
💬 **Reply to Admin**

Write your message to send to the admin:

Example: Thank you for your help! I have a question about...

Please type your reply:
"""

    context.user_data['replying_to_admin'] = admin_id
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(reply_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_reply_to_admin_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user reply to admin message input"""
    if not update.message or not update.message.text:
        return

    admin_id = context.user_data.get('replying_to_admin')
    if not admin_id:
        return

    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "User"
    message_text = update.message.text.strip()

    try:
        # Send message to admin
        await context.bot.send_message(
            chat_id=admin_id, 
            text=f"💬 **Reply from User:**\n\n👤 **User:** {user_name} (ID: {user_id})\n📩 **Message:** {message_text}",
            parse_mode='Markdown'
        )

        # Confirm to user
        await update.message.reply_text(
            "✅ **Your reply has been sent to the admin!**\n\nThey will get back to you soon.",
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text("❌ Failed to send your reply. Please try again later.")
        logger.error(f"Failed to send reply to admin {admin_id}: {e}")

    # Clear context
    context.user_data.pop('replying_to_admin', None)

async def admin_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route admin messages based on context"""
    admin_id = str(update.effective_user.id)
    if admin_id != ADMIN_CHAT_ID:
        return

    text = update.message.text.strip() if update.message and update.message.text else ""
    
    # Handle Reply Keyboard buttons for admin
    reply_keyboard_buttons = ["💸 Sell Account", "🏦 Withdrawal", "💰 Balance", "ℹ️ Safety & Terms"]
    if text in reply_keyboard_buttons:
        # Forward to handle_reply_keyboard logic
        logger.info(f"Reply Keyboard pressed: '{text}' by admin {admin_id}")
        
        class FakeQuery:
            def __init__(self, original_update):
                self.from_user = original_update.effective_user
                self.message = original_update.message
                self.data = None

            async def answer(self, text=None, show_alert=False):
                pass

            async def edit_message_text(self, text, **kwargs):
                await update.message.reply_text(text, **kwargs)

            async def edit_message_reply_markup(self, reply_markup=None):
                await update.message.reply_text("Choose an option:", reply_markup=reply_markup)

        class FakeUpdate:
            def __init__(self, original_update, fake_query):
                self.effective_user = original_update.effective_user
                self.effective_chat = original_update.effective_chat
                self.callback_query = fake_query

        fake_query = FakeQuery(update)
        fake_update = FakeUpdate(update, fake_query)

        if text == "💸 Sell Account":
            await sell_account_callback(fake_update, context)
        elif text == "🏦 Withdrawal":
            await withdrawal_callback(fake_update, context)
        elif text == "💰 Balance":
            await balance_callback(fake_update, context)
        elif text == "ℹ️ Safety & Terms":
            await terms_command(update, context)
        return

    # Check if admin is in operation mode
    if 'admin_operation' in context.user_data:
        await handle_admin_amount_input(update, context)
    elif 'admin_balance_type' in context.user_data:
        await handle_admin_user_id_input(update, context)
    elif 'admin_add_new_country' in context.user_data and 'new_country_name' not in context.user_data:
        await handle_admin_new_country_name_input(update, context)
    elif 'admin_add_new_country' in context.user_data and 'new_country_name' in context.user_data:
        await handle_admin_new_country_price_input(update, context)
    elif 'price_control_country' in context.user_data:
        await handle_admin_price_change_input(update, context)
    elif 'admin_sms_all_users' in context.user_data:
        await handle_admin_sms_all_users_input(update, context)
    elif 'admin_sms_single_user' in context.user_data and 'sms_target_user' not in context.user_data:
        await handle_admin_sms_single_user_id_input(update, context)
    elif 'sms_target_user' in context.user_data:
        await handle_admin_sms_single_user_message_input(update, context)
    elif 'admin_chat_user' in context.user_data and 'chat_target_user' not in context.user_data:
        await handle_admin_chat_user_id_input(update, context)
    elif 'chat_target_user' in context.user_data:
        await handle_admin_chat_user_message_input(update, context)
    elif 'replying_to_admin' in context.user_data:
        await handle_reply_to_admin_message_input(update, context)
    elif 'admin_withdrawal_all_set' in context.user_data:
        await handle_admin_withdrawal_all_set_input(update, context)
    elif 'admin_withdrawal_custom_user' in context.user_data and 'withdrawal_limit_target_user' not in context.user_data:
        await handle_admin_withdrawal_custom_user_id_input(update, context)
    elif 'withdrawal_limit_target_user' in context.user_data:
        await handle_admin_withdrawal_custom_user_limit_input(update, context)
    elif 'reject_sms_user_id' in context.user_data:
        await handle_reject_sms_message_input(update, context)
    elif 'reject_pin_sms_user_id' in context.user_data:
        await handle_reject_pin_sms_message_input(update, context)
    # If no specific context, ignore the message

async def handle_buy_country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle buying account from specific country"""
    query = update.callback_query
    await query.answer()

    # Extract country key from callback data: buy_country_{country_key}
    country_key = query.data.split('_', 2)[2]

    if country_key not in COUNTRIES_DATA:
        await query.edit_message_text("❌ Country data not found!")
        return

    country_data = COUNTRIES_DATA[country_key]
    # Calculate 30% higher price for buying
    buy_price = country_data['buy_price']

    user_id = str(query.from_user.id)
    user_info = get_user_data(user_id)

    # Check Top-Up balance (as per user requirement)
    if user_info['topup_balance_usdt'] >= buy_price:
        # Deduct from Top-Up balance and increment bought accounts
        user_info['topup_balance_usdt'] -= buy_price
        user_info['accounts_bought'] += 1
        save_user_data()

        success_text = f"""
✅ **Purchase Successful!**

🌍 **Country:** {country_data['name']}
💰 **Cost:** ${buy_price} USD
💳 **Current Top-Up Balance:** {user_info['topup_balance_usdt']:.2f} USDT

📧 Account details will be sent to your inbox soon.

🎉 Thank you for using our service!
"""
        keyboard = [
            [InlineKeyboardButton("🛒 Buy More", callback_data="buy_account")],
            [InlineKeyboardButton("💰 View Balance", callback_data="balance")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
    else:
        needed = buy_price - user_info['topup_balance_usdt']
        success_text = f"""
❌ **Insufficient Top-Up Balance!**

🌍 **Country:** {country_data['name']}
💰 **Required:** ${buy_price} USD
💳 **Your Top-Up Balance:** {user_info['topup_balance_usdt']:.2f} USDT
🔺 **Additional Required:** ${needed:.2f} USD

💳 Please top-up your balance first.
"""
        keyboard = [
            [InlineKeyboardButton("💳 Top-Up Balance", callback_data="topup")],
            [InlineKeyboardButton("💰 View Balance", callback_data="balance")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')

async def placeholder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Placeholder for features under development"""
    query = update.callback_query
    await query.answer("This feature is coming soon! 🚧", show_alert=True)

async def handle_reply_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Reply Keyboard button presses"""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    logger.info(f"Reply Keyboard pressed: '{text}' by user {update.effective_user.id}")

    # Create a fake callback query object for compatibility with existing handlers
    class FakeQuery:
        def __init__(self, user_id):
            self.from_user = update.effective_user
            self.message = update.message
            self.data = None  # Add data attribute

        async def answer(self, text=None, show_alert=False):
            pass

        async def edit_message_text(self, text, **kwargs):
            await update.message.reply_text(text, **kwargs)

        async def edit_message_reply_markup(self, reply_markup=None):
            await update.message.reply_text("Choose an option:", reply_markup=reply_markup)

    # Create a simple fake update object
    class FakeUpdate:
        def __init__(self, original_update, fake_query):
            self.effective_user = original_update.effective_user
            self.effective_chat = original_update.effective_chat
            self.callback_query = fake_query

    fake_query = FakeQuery(update.effective_user.id)
    fake_update = FakeUpdate(update, fake_query)

    # Map Reply Keyboard buttons to callback functions
    if text == "💸 Sell Account":
        await sell_account_callback(fake_update, context)
    elif text == "🏦 Withdrawal":
        await withdrawal_callback(fake_update, context)
    elif text == "💰 Balance":
        await balance_callback(fake_update, context)
    elif text == "ℹ️ Safety & Terms":
        await terms_command(update, context)
    elif text == "👥 Refer & Earn":
        await refer_callback(fake_update, context)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main callback query handler"""
    query = update.callback_query
    data = query.data

    # Handle admin approval callbacks
    if data and data.startswith('approve_sell_'):
        await approve_sell_callback(update, context)
        return
    if data and data.startswith('reject_sell_'):
        await reject_sell_callback(update, context)
        return
    if data and data.startswith('approve_'):
        await approve_callback(update, context)
        return

    # Handle admin add/remove balance callbacks
    if data and (data.startswith('admin_add_') or data.startswith('admin_remove_')):
        await admin_add_remove_callback(update, context)
        return

    # Handle buy country callbacks
    if data and data.startswith('buy_country_'):
        await handle_buy_country_callback(update, context)
        return
    
    # Handle admin edit sell price callbacks
    if data and data.startswith('admin_edit_sell_'):
        await admin_edit_sell_price_callback(update, context)
        return

    # Handle reply to admin callbacks
    if data and data.startswith('reply_admin_'):
        await reply_to_admin_callback(update, context)
        return

    handlers = {
        'balance': balance_callback,
        'buy_account': buy_account_callback,
        'sell_account': sell_account_callback,
        'topup': topup_callback,
        'withdrawal': withdrawal_callback,
        'buy_premium': buy_premium_callback,
        'buy_standard': buy_standard_callback,
        'buy_basic': buy_basic_callback,
        'main_menu': main_menu_callback,

        # Country region handlers
        'countries_europe': countries_europe_callback,
        'countries_asia': countries_asia_callback,
        'countries_africa': countries_africa_callback,
        'countries_america': countries_america_callback,
        'countries_others': countries_others_callback,

        # Admin handlers
        'admin_panel': admin_panel_callback,
        'admin_main_balance': lambda u, c: admin_balance_control_start(u, c, 'main'),
        'admin_hold_balance': lambda u, c: admin_balance_control_start(u, c, 'hold'),
        'admin_price_control': admin_price_control_callback,
        'admin_sell_price_control': admin_sell_price_control_callback,
        'admin_buy_price_control': admin_buy_price_control_callback,
        'admin_topup_info': admin_topup_info_callback,
        'admin_send_sms': admin_send_sms_callback,
        'admin_chat_user': admin_chat_user_callback,
        'admin_sms_all_users': admin_sms_all_users_callback,
        'admin_sms_single_user': admin_sms_single_user_callback,
        'admin_add_new_country': admin_add_new_country_callback,
        'admin_withdrawal_set': admin_withdrawal_set_callback,
        'admin_withdrawal_all_set': admin_withdrawal_all_set_callback,
        'admin_withdrawal_custom_user': admin_withdrawal_custom_user_callback,

        # Reply to admin handler  
        'reply_admin': reply_to_admin_callback,

        # Withdrawal method handlers
        'withdraw_binance': withdraw_binance_callback,
        'withdraw_payeer': withdraw_payeer_callback,
        'withdraw_trc20': withdraw_trc20_callback,
        'withdraw_bep20': withdraw_bep20_callback,
        'withdraw_paypal': withdraw_paypal_callback,
        'withdraw_bitcoin': withdraw_bitcoin_callback,
        'withdraw_cashapp': withdraw_cashapp_callback,
        'withdraw_upi': withdraw_upi_callback,
        'withdraw_bank': withdraw_bank_callback,

        # Top-up payment method handlers
        'topup_binance': topup_binance_callback,
        'topup_payeer': topup_payeer_callback,
        'topup_trc20': topup_trc20_callback,
        'topup_bep20': topup_bep20_callback,
        'topup_arbitrum': topup_arbitrum_callback,

        # Terms handler  
        'terms': lambda u, c: terms_command(u, c),

        # Refer handler
        'refer': refer_callback,

        # Placeholder handlers for other sub-features
        'submit_account': placeholder_callback,
    }

    handler = handlers.get(data, placeholder_callback)
    await handler(update, context)

async def pii_guard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guard against users accidentally sharing phone numbers or verification codes"""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    # Patterns to detect phone numbers and verification codes
    phone_patterns = [
        r'\+?\d{10,15}',  # Phone numbers with optional +
        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # US format
        r'\(\d{3}\)\s?\d{3}[-.\s]?\d{4}',  # (xxx) xxx-xxxx format
    ]

    code_patterns = [
        r'^[0-9]{4,8}$',  # 4-8 digit codes
        r'\b[0-9]{4,8}\b',  # 4-8 digit codes in text
    ]

    # Check for phone numbers
    for pattern in phone_patterns:
        if re.search(pattern, text):
            warning_text = """
⚠️ **Security Warning!**

We do not collect phone numbers.

🚫 **Please do not share phone numbers.**

💡 This is a demo/test bot. All activities are for testing purposes only.

Return to main menu with /start.
"""
            await update.message.reply_text(warning_text, parse_mode='Markdown')
            return

    # Check for verification codes
    for pattern in code_patterns:
        if re.search(pattern, text):
            warning_text = """
⚠️ **Security Warning!**

We do not collect verification codes.

🚫 **Please do not share any codes.**

💡 This is a demo/test bot. No OTP or verification required.

Return to main menu with /start.
"""
            await update.message.reply_text(warning_text, parse_mode='Markdown')
            return

async def terms_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show safety terms and conditions"""
    terms_text = """
ℹ️ **Safety & Terms of Use for the Bot**

Thank you for using our bot! Before you proceed, please carefully read the following safety guidelines and terms of service. By using the bot, you are considered to have agreed to these terms.

🛡️ **Safety Guidelines**

We have established some rules to ensure a safe and positive environment for all users. Adherence to these rules is mandatory:

• **No Spamming:** Refrain from sending any form of spam or unnecessary messages using the bot.
• **Hate Speech and Harassment are Prohibited:** The bot must not be used to attack any race, religion, ethnicity, gender, or group, or to harass any individual.
• **Illegal Activities:** Using the bot for any illegal activities, such as making threats, engaging in fraud, or sharing illegal information, is strictly forbidden.
• **Abuse of the Bot:** Do not exploit any bugs or glitches in the bot or attempt to crash it.
• **Protection of Personal Information:** Do not attempt to collect or share the personal information of other users through the bot.

Violation of these rules may result in you being banned from using the bot.

📜 **Terms of Service**

**1. Acceptance of Terms:**
By using this bot, you fully agree to our Terms of Service. If you do not agree with these terms, you are requested not to use the bot.

**2. Data and Privacy:**
• **Data Collection:** To function correctly, the bot may collect some basic information, such as your User ID and Server ID. We do not collect your personal messages or any sensitive information.
• **Use of Data:** The collected data is used solely to improve the bot's functionality and enhance the user experience. We do not sell or share your data with any third parties.

**3. Changes and Termination of Service:**
We reserve the right to modify, suspend, or completely terminate the bot's services at any time without prior notice.

**4. Limitation of Liability:**
The bot is provided on an "as is" basis. The bot developer will not be liable for any direct or indirect damages to you or your server resulting from its use. We do not guarantee the bot's constant availability or accuracy.

**5. Changes to Terms:**
We reserve the right to change these terms from time to time. We will attempt to notify you of any major changes. Your continued use of the bot after any modifications will be considered your acceptance of the new terms.

Thank you again for using our bot. For any questions or feedback, please contact us.

Return to main menu with /start.
"""

    keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(terms_text, reply_markup=reply_markup, parse_mode='Markdown')

def main() -> None:
    """Start the bot"""
    # Load existing user data
    load_user_data()
    
    # Load withdrawal settings
    load_withdrawal_settings()

    # Bot token - hardcoded for portability
    token = "8198086071:AAGwOzZDl60-vNjfujt2hl_0Qm6cPESDi6g"

    # Create application
    application = Application.builder().token(token).build()

    # Create conversation handler for sell account flow
    sell_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(country_selection_handler, pattern=r'^select_')],
        states={
            WAITING_FOR_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_number_input)],
            WAITING_FOR_ADMIN_APPROVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pin_input)],
            WAITING_FOR_PIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pin_input)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_sell_conversation, pattern=r'^sell_account$'),
            CommandHandler('start', start)
        ],
        per_message=False,
        per_chat=True,
        per_user=True,
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("terms", terms_command))
    application.add_handler(sell_conversation)
    
    # Add explicit admin callback handlers (higher priority - before generic callback handler)
    application.add_handler(CallbackQueryHandler(admin_panel_callback, pattern="^admin_panel$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: admin_balance_control_start(u, c, 'main'), pattern="^admin_main_balance$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: admin_balance_control_start(u, c, 'hold'), pattern="^admin_hold_balance$"))
    application.add_handler(CallbackQueryHandler(approve_sell_callback, pattern="^approve_sell_"))
    application.add_handler(CallbackQueryHandler(reject_sell_callback, pattern="^reject_sell_"))
    application.add_handler(CallbackQueryHandler(reject_sms_callback, pattern="^reject_sms_"))
    application.add_handler(CallbackQueryHandler(reject_pin_callback, pattern="^reject_pin_"))
    application.add_handler(CallbackQueryHandler(reject_pin_sms_callback, pattern="^reject_pin_sms_"))
    application.add_handler(CallbackQueryHandler(approve_callback, pattern="^approve_\d+_\d+(\.\d+)?$"))
    application.add_handler(CallbackQueryHandler(admin_sell_price_control_callback, pattern="^admin_sell_price_control$"))
    application.add_handler(CallbackQueryHandler(admin_buy_price_control_callback, pattern="^admin_buy_price_control$"))
    application.add_handler(CallbackQueryHandler(admin_topup_info_callback, pattern="^admin_topup_info$"))
    application.add_handler(CallbackQueryHandler(admin_send_sms_callback, pattern="^admin_send_sms$"))
    application.add_handler(CallbackQueryHandler(admin_chat_user_callback, pattern="^admin_chat_user$"))
    application.add_handler(CallbackQueryHandler(admin_add_new_country_callback, pattern="^admin_add_new_country$"))
    application.add_handler(CallbackQueryHandler(admin_delete_country_callback, pattern="^admin_delete_country$"))
    application.add_handler(CallbackQueryHandler(admin_confirm_delete_country_callback, pattern="^admin_del_country_"))
    application.add_handler(CallbackQueryHandler(admin_withdrawal_set_callback, pattern="^admin_withdrawal_set$"))
    application.add_handler(CallbackQueryHandler(admin_withdrawal_all_set_callback, pattern="^admin_withdrawal_all_set$"))
    application.add_handler(CallbackQueryHandler(admin_withdrawal_custom_user_callback, pattern="^admin_withdrawal_custom_user$"))
    
    # Generic callback handler (lower priority - catches remaining callbacks)
    application.add_handler(CallbackQueryHandler(callback_handler))

    # Add Reply Keyboard handler (higher priority - before other text handlers, but exclude admin messages)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Chat(ADMIN_CHAT_ID_INT), handle_reply_keyboard))

    # Add admin message router (medium priority)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Chat(ADMIN_CHAT_ID_INT), admin_message_router))

    # Add PII guard for all text messages (but not commands) - lower priority
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, pii_guard_handler))

    # Log startup
    logger.info("Starting Telegram Account Trading Bot...")
    logger.info(f"Loaded data for {len(user_data)} existing users")

    # Start the bot
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
