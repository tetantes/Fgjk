import os
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = 6011460052
CHANNEL = "@freearningstetantes"
class BotData:
    def __init__(self):
        self.required_channels = {"@freearningstetantes"}
        self.users = {}
        self.referral_amount = 0.5  # STAR per referral
        self.min_withdrawal = 1  # Minimum STAR for withdrawal
        self.max_withdrawal = 10  # Maximum STAR for withdrawal
        self.withdrawal_open = True
        self.withdrawal_channels = ["@freearningstetantes"]  # Default withdrawal channel

# Initialize bot data
bot_data = BotData()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Show welcome message with verification buttons
    keyboard = []
    for channel in bot_data.required_channels:
        channel_name = channel[1:] # Remove @ symbol
        try:
            chat = await context.bot.get_chat(channel)
            invite_link = chat.invite_link
            if not invite_link:
                invite_link = await context.bot.create_chat_invite_link(chat.id)
                invite_link = invite_link.invite_link
        except Exception as e:
            print(f"Error getting invite link for {channel}: {e}")
            invite_link = f"https://t.me/{channel_name}"
        
        keyboard.append([InlineKeyboardButton(f"Join {channel}", url=invite_link)])
    
    keyboard.append([InlineKeyboardButton("✅ Check Membership", callback_data="check_membership")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🌟 Welcome to STAR Reaction Bot! ⭐\n\n"
        "⚠️ You must join our channels to use the bot!\n"
        "After joining, click verify button below to start earning ⭐",
        reply_markup=reply_markup
    )

    # Stop here if user is not a member
    is_member = await check_member(user_id, context.bot)
    if not is_member:
        return

    # Handle referral
    if context.args and context.args[0].startswith('REF'):
        try:
            referrer_id = int(context.args[0][3:])  # Extract ID from REF code
            
            # Make sure referrer exists and is not self-referring
            if referrer_id in bot_data.users and referrer_id != user_id:
                referrer = await context.bot.get_chat(referrer_id)
                
                # Initialize referrer's referral data if needed
                if 'pending_referrals' not in bot_data.users[referrer_id]:
                    bot_data.users[referrer_id]['pending_referrals'] = []
                if 'completed_referrals' not in bot_data.users[referrer_id]:
                    bot_data.users[referrer_id]['completed_referrals'] = []
                
                # Check if user hasn't been referred before
                if (user_id not in bot_data.users[referrer_id]['pending_referrals'] and 
                    user_id not in [ref['user_id'] for ref in bot_data.users[referrer_id].get('completed_referrals', [])]):
                    
                    # Initialize new user data
                    bot_data.users[user_id] = {
                        'balance': 0,
                        'referrals': 0,
                        'referral_code': f"REF{user_id}",
                        'wallet': None,
                        'referred_by': referrer_id
                    }
                    
                    # Add to pending referrals
                    bot_data.users[referrer_id]['pending_referrals'].append(user_id)
                    
                    # Send notification messages
                    await update.message.reply_text(
                        f"✨ Welcome! You were referred by @{referrer.username}!\n"
                        "Join all channels and verify membership to activate the referral reward!"
                    )
                    
                    # Notify referrer about new referral
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 New referral! @{update.effective_user.username} joined using your link!\n"
                             "They need to verify channel membership to activate your reward."
                    )
                    
                    print(f"Added pending referral: {user_id} for referrer: {referrer_id}")
        except Exception as e:
            print(f"Referral error: {e}")
            await update.message.reply_text("❌ There was an error processing the referral. Please try again.")


    # Register new user if needed
    if user_id not in bot_data.users:
        bot_data.users[user_id] = {
            'balance': 0,
            'referrals': 0,
            'referral_code': f"REF{user_id}",
            'wallet': None
        }

async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = bot_data.users[user_id]
    bot = await context.bot.get_me()
    referral_link = f"https://t.me/{bot.username}?start={user_data['referral_code']}"

    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        f"🔗 Your referral link: {referral_link}\n"
        f"⭐ Reward per referral: {bot_data.referral_amount} ⭐\n"  # Added line showing reward per referral
        f"👥 Total referrals: {user_data['referrals']}\n"
        f"💰 Earned from referrals: {user_data['referrals'] * bot_data.referral_amount} ⭐"
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, override_command=None):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use admin commands.")
        return

    command = override_command if override_command else (context.args[0] if context.args else None)
    if not command:
        await update.message.reply_text("Please specify a command. Use /admin help for available commands.")
        return
    context.args = context.args[1:] if not override_command else context.args

    if command == "help":
        help_text = (
            "ℹ️ Available Admin Commands:\n\n"
            "💰 Balance Management:\n"
            "/add_balance [user_id] [amount] - Add balance to user\n"
            "/deduct_balance [user_id] [amount] - Deduct balance from user\n\n"
            "频道管理:\n"
            "/add_channel [channel] - Add a required channel\n"
            "/remove_channel [channel] - Remove a required channel\n"
            "/add_withdrawal_channel [channel] - Add a withdrawal channel\n"
            "/remove_withdrawal_channel [channel] - Remove a withdrawal channel\n\n"
            "⚙️ Settings:\n"
            "/set_min_withdrawal [amount] - Set minimum withdrawal amount\n"
            "/set_referral_amount [amount] - Set referral reward amount\n"
            "/toggle_withdrawal - Toggle withdrawals on/off"
        )
        await update.message.reply_text(help_text)
        return

    if command == "add_balance":
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /admin add_balance [user_id] [amount]")
            return
        try:
            user_id = int(context.args[0])
            amount = int(context.args[1])
            if user_id not in bot_data.users:
                bot_data.users[user_id] = {'balance': 0, 'referrals': 0, 'referral_code': f"REF{user_id}"}
            bot_data.users[user_id]['balance'] += amount
            await update.message.reply_text(f"Added {amount} ⭐ to user {user_id}")
        except ValueError:
            await update.message.reply_text("Invalid user_id or amount")
            return

    elif command == "deduct_balance":
        if len(context.args) != 2:
            await update.message.reply_text("Usage: /admin deduct_balance [user_id] [amount]")
            return
        try:
            user_id = int(context.args[0])
            amount = int(context.args[1])
            if user_id in bot_data.users:
                if bot_data.users[user_id]['balance'] >= amount:
                    bot_data.users[user_id]['balance'] -= amount
                    await update.message.reply_text(f"Deducted {amount} ⭐ from user {user_id}")
                else:
                    await update.message.reply_text("User doesn't have enough balance")
            else:
                await update.message.reply_text("User not found")
        except ValueError:
            await update.message.reply_text("Invalid user_id or amount")
            return

    if command == "add_channel":
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /add_channel [channel]\nExample: /add_channel @channelname")
            return
        channel = context.args[1]
        if not channel.startswith('@'):
            channel = '@' + channel
        bot_data.required_channels.add(channel)
        await update.message.reply_text(f"✅ Added channel: {channel}\nCurrent channels: {', '.join(bot_data.required_channels)}")

    elif command == "remove_channel":
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /remove_channel [channel]\nExample: /remove_channel @channelname")
            return
        channel = context.args[1]
        if not channel.startswith('@'):
            channel = '@' + channel
        try:
            bot_data.required_channels.remove(channel)
            await update.message.reply_text(f"✅ Removed channel: {channel}\nRemaining channels: {', '.join(bot_data.required_channels)}")
        except KeyError:
            await update.message.reply_text(f"⚠️ Channel {channel} not found in required channels!\nCurrent channels: {', '.join(bot_data.required_channels)}")

    elif command == "set_min_withdrawal":
        amount = int(context.args[1])
        bot_data.min_withdrawal = amount
        await update.message.reply_text(f"Set minimum withdrawal to {amount} DOGS")

    elif command == "set_referral_amount":
        amount = int(context.args[1])
        bot_data.referral_amount = amount
        await update.message.reply_text(f"Set referral amount to {amount} DOGS")

    elif command == "toggle_withdrawal":
        bot_data.withdrawal_open = not bot_data.withdrawal_open
        status = "opened" if bot_data.withdrawal_open else "closed"
        await update.message.reply_text(f"Withdrawals are now {status}")

    elif command == "add_withdrawal_channel":
        if len(context.args) != 2:
            await update.message.reply_text("Usage: /add_withdrawal_channel [channel]")
            return
        channel = context.args[1]
        if channel not in bot_data.withdrawal_channels:
            bot_data.withdrawal_channels.append(channel)
            await update.message.reply_text(f"Added withdrawal channel: {channel}")
        else:
            await update.message.reply_text("Channel already exists!")

    elif command == "remove_withdrawal_channel":
        if len(context.args) != 2:
            await update.message.reply_text("Usage: /remove_withdrawal_channel [channel]")
            return
        channel = context.args[1]
        if channel in bot_data.withdrawal_channels:
            bot_data.withdrawal_channels.remove(channel)
            await update.message.reply_text(f"Removed withdrawal channel: {channel}")
        else:
            await update.message.reply_text("Channel not found!")

async def ensure_user_exists(user_id: int):
    if user_id not in bot_data.users:
        bot_data.users[user_id] = {
            'balance': 0,
            'referrals': 0,
            'referral_code': f"REF{user_id}",
            'wallet': None
        }

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await ensure_user_exists(user_id)

    if query.data != "check_membership":
        is_member = await check_member(user_id, context.bot)
        if not is_member:
            await query.answer("⚠️ Please join our channels first!", show_alert=True)
            return

    if query.data == "profile":
        user_data = bot_data.users[user_id]
        await query.answer()
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")]]
        await query.message.edit_text(
            f"👤 Your Profile\n\n"
            f"📱 User ID: {user_id}\n"
            f"💰 Balance: {user_data['balance']} ⭐\n"
            f"👥 Referrals: {user_data['referrals']}\n"
            f"📝 Post Link: {user_data.get('wallet', 'Not set')}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "withdraw":
        if not bot_data.withdrawal_open:
            await query.answer("Withdrawals are currently closed!")
            return

        if not bot_data.users[user_id].get('wallet'):
            await query.answer("⚠️ Please set your post link first!", show_alert=True)
            return

        balance = bot_data.users[user_id]['balance']
        if balance < bot_data.min_withdrawal:
            await query.message.reply_text("⚠️ Not enough balance for withdrawal!")

        withdrawal_keyboard = [
            [InlineKeyboardButton(f"1⭐", callback_data="withdraw_1"),
             InlineKeyboardButton(f"2⭐", callback_data="withdraw_2")],
            [InlineKeyboardButton(f"3⭐", callback_data="withdraw_3"),
             InlineKeyboardButton(f"4⭐", callback_data="withdraw_4")],
            [InlineKeyboardButton(f"5⭐", callback_data="withdraw_5"),
             InlineKeyboardButton(f"6⭐", callback_data="withdraw_6")],
            [InlineKeyboardButton(f"7⭐", callback_data="withdraw_7")]
        ]
        await query.message.reply_text(
            f"💳 Select the amount to withdraw\n\nBalance: {balance}⭐\n\n" + "\n".join([f"{channel} - withdrawals channel" for channel in bot_data.withdrawal_channels]),
            reply_markup=InlineKeyboardMarkup(withdrawal_keyboard)
        )
        return

    elif query.data.startswith("withdraw_"):
        amount = int(query.data.split("_")[1])
        balance = bot_data.users[user_id]['balance']

        if balance < amount:
            await query.answer("⚠️ Not enough balance!", show_alert=True)
            return

        user_post_link = bot_data.users[user_id].get('wallet', 'Not set')
        user = await context.bot.get_chat(user_id)
        bot = await context.bot.get_me()

        # Create withdrawal message
        withdrawal_msg = (f"⭐ New Withdrawal Request (PENDING)\n\n"
                        f"👤 User: {user_id} (@{user.username if user.username else 'no username'})\n"
                        f"💰 Amount: {amount}⭐\n"
                        f"📝 Post Link: {user_post_link}\n"
                        f"🤖 Bot: @{bot.username}")

        # Deduct the balance
        bot_data.users[user_id]['balance'] -= amount

        # Send to admin and withdrawal channel
        await context.bot.send_message(chat_id=ADMIN_ID, text=withdrawal_msg)
        await context.bot.send_message(chat_id="@STAR_REACTION_PAYOUT", text=withdrawal_msg)

        await query.answer("Withdrawal request sent to admin!")

        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")]]
        await query.message.edit_text("Withdrawal request sent! Click below to go back.", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "referral":
        await handle_referral(update, context)

    elif query.data == "promotion":
        await query.answer()
        await query.message.reply_text("For promotion of your channel D.M @SPIDERMAN383")

    elif query.data == "set_wallet":
        await query.answer()
        msg = await query.message.reply_text("Send your post link where you want to receive your stars ⭐")
        context.user_data['expecting_wallet'] = True

    elif query.data == "back_to_main":
        keyboard = [
            [InlineKeyboardButton("👤 Profile", callback_data="profile"),
             InlineKeyboardButton("⭐ Earn Stars", callback_data="referral")],
            [InlineKeyboardButton("💎 Withdraw Stars", callback_data="withdraw")],
            [InlineKeyboardButton("📝 Set Post Link", callback_data="set_wallet")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Select an option:", reply_markup=reply_markup)

    elif query.data == "check_membership":
        is_member = await check_member(user_id, context.bot)
        if is_member:
            await query.answer("✅ Membership verified!")

            # Check if this user was referred
            if user_id in bot_data.users and 'referred_by' in bot_data.users[user_id]:
                    referrer_id = bot_data.users[user_id]['referred_by']

                    # Initialize referrer data structures if needed
                    if referrer_id not in bot_data.users:
                        bot_data.users[referrer_id] = {
                            'balance': 0,
                            'referrals': 0,
                            'referral_code': f"REF{referrer_id}",
                            'wallet': None,
                            'pending_referrals': [],
                            'completed_referrals': []
                        }

                    if 'pending_referrals' not in bot_data.users[referrer_id]:
                        bot_data.users[referrer_id]['pending_referrals'] = []
                    if 'completed_referrals' not in bot_data.users[referrer_id]:
                        bot_data.users[referrer_id]['completed_referrals'] = []

                    # Check if referral is pending and not already completed
                    completed_refs = [ref['user_id'] for ref in bot_data.users[referrer_id]['completed_referrals']]
                    if user_id in bot_data.users[referrer_id]['pending_referrals'] and user_id not in completed_refs:
                        # Convert pending referral to completed
                        bot_data.users[referrer_id]['pending_referrals'].remove(user_id)
                        bot_data.users[referrer_id]['completed_referrals'].append({
                            'user_id': user_id,
                            'username': update.effective_user.username,
                            'date': str(datetime.datetime.now())
                        })
                        bot_data.users[referrer_id]['referrals'] += 1
                        bot_data.users[referrer_id]['balance'] += bot_data.referral_amount

                    # Notify referrer
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 Referral Success! @{update.effective_user.username} verified their membership!\n"
                        f"You earned {bot_data.referral_amount} ⭐!"
                    )
                    print(f"Completed referral: {user_id} for referrer: {referrer_id}")
            keyboard = [
                [InlineKeyboardButton("👤 Profile", callback_data="profile"),
                 InlineKeyboardButton("⭐ Earn Stars", callback_data="referral")],
                [InlineKeyboardButton("💎 Withdraw Stars", callback_data="withdraw")],
                [InlineKeyboardButton("📝 Set Post Link", callback_data="set_wallet")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(
                    "Select an option:",
                    reply_markup=reply_markup
                )
            except:
                await query.message.reply_text(
                    "Select an option:",
                    reply_markup=reply_markup
                )
        else:
            await query.answer("⚠️ Please join all required channels first!", show_alert=True)

async def check_member(user_id: int, bot) -> bool:
    for channel in bot_data.required_channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                print(f"User {user_id} not member of {channel}")
                return False
        except Exception as e:
            print(f"Error checking membership for {channel}: {e}")
            try:
                # Retry with numeric channel ID if possible
                chat = await bot.get_chat(channel)
                member = await bot.get_chat_member(chat_id=chat.id, user_id=user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    return False
            except Exception as retry_e:
                print(f"Retry failed for {channel}: {retry_e}")
                return False
    return True

def main():
    try:
        print("Starting bot...")
        application = Application.builder().token(TELEGRAM_TOKEN).build()

        async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            print(f"Error occurred: {context.error}")

        application.add_error_handler(error_handler)

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("admin", admin_command))

        async def wrap_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, cmd: str):
            if update.effective_user.id != ADMIN_ID:
                await update.message.reply_text("⚠️ You are not authorized to use this command.")
                return
            await admin_command(update, context, override_command=cmd)

        application.add_handler(CommandHandler("help", lambda u,c: wrap_admin_command(u,c, "help")))
        application.add_handler(CommandHandler("add_balance", lambda u,c: wrap_admin_command(u,c, "add_balance")))
        application.add_handler(CommandHandler("deduct_balance", lambda u,c: wrap_admin_command(u,c, "deduct_balance")))
        application.add_handler(CommandHandler("add_channel", lambda u,c: wrap_admin_command(u,c, "add_channel")))
        application.add_handler(CommandHandler("remove_channel", lambda u,c: wrap_admin_command(u,c, "remove_channel")))
        application.add_handler(CommandHandler("set_min_withdrawal", lambda u,c: wrap_admin_command(u,c, "set_min_withdrawal")))
        application.add_handler(CommandHandler("set_referral_amount", lambda u,c: wrap_admin_command(u,c, "set_referral_amount")))
        application.add_handler(CommandHandler("toggle_withdrawal", lambda u,c: wrap_admin_command(u,c, "toggle_withdrawal")))
        application.add_handler(CommandHandler("add_withdrawal_channel", lambda u,c: wrap_admin_command(u,c, "add_withdrawal_channel")))
        application.add_handler(CommandHandler("remove_withdrawal_channel", lambda u,c: wrap_admin_command(u,c, "remove_withdrawal_channel")))
        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if 'expecting_wallet' in context.user_data and context.user_data['expecting_wallet']:
                user_id = update.effective_user.id
                post_link = update.message.text
                bot_data.users[user_id]['wallet'] = post_link
                context.user_data['expecting_wallet'] = False
                await update.message.reply_text("✅ Your post link has been saved successfully!")
            else:
                print(f"Received message: {update.message.text}")

        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("Bot is running! Press Ctrl+C to stop.")
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        print(f"Error starting bot: {e}")

if __name__ == "__main__":
    main()
