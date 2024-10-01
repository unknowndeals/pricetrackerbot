#main.py



from pyrogram import Client, filters  # Pyrogram is an async Telegram API wrapper. Ensure it is installed (`pip install pyrogram`).
from pyrogram.types import Message, InputMediaPhoto
from dotenv import load_dotenv  # Used for environment variable management (`pip install python-dotenv`).
import os
import re
import asyncio
import schedule  # Used for task scheduling. Ensure it's installed (`pip install schedule`).
import pytz  # For timezone management. Install if needed (`pip install pytz`).
from pymongo import MongoClient  # MongoDB client library (`pip install pymongo`).
import datetime
import time
import threading
import requests  # For making HTTP requests (`pip install requests`).
import json
from bson import ObjectId  # Used to work with MongoDB object IDs. Comes with pymongo.
import logging

# Import functions from your other files
from scraper import scrape
from scheduler import check_prices
from helpers import fetch_all_products, add_new_product, fetch_one_product, delete_one, update_product_price, fetch_global_product
from regex_patterns import flipkart_patterns, amazon_patterns, all_url_patterns  # Ensure this file exists and patterns are correctly defined.
from tenacity import retry, stop_after_attempt, wait_exponential
from motor.motor_asyncio import AsyncIOMotorClient  # For async MongoDB operations (`pip install motor`).


# Load environment variables

load_dotenv()



# Get environment variables

bot_token = os.getenv("BOT_TOKEN")

api_id = os.getenv("API_ID")

api_hash = os.getenv("API_HASH")

EARNKARO_API_TOKEN = os.getenv("EARNKARO_API_TOKEN")



# MongoDB connection

dbclient = AsyncIOMotorClient(os.getenv("MONGO_URI"))

database = dbclient[os.getenv("DATABASE")]

users_collection = database["Users"]



LOG_CHANNEL_ID = -1002493553437 # Replace with your log channel ID

ADMINS = [1720819569] # Replace with actual admin user ID(s)



# Set up logging

logging.basicConfig(level=logging.INFO)



# Function to log new users

async def log_new_user(user_id, username):
    user = {
        "user_id": user_id,
        "username": username,
        "joined_at": datetime.datetime.now(datetime.timezone.utc)
    }
    
    try:
        existing_user = await users_collection.find_one({"user_id": user_id})
        if not existing_user:
            await users_collection.insert_one(user)
            return True
        return False
    except Exception as e:
        logging.error(f"MongoDB Error: {e}")
        return False




# Initialize the bot

app = Client("PriceTrackerBot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)



# Function to expand short URLs

def expand_short_url(short_url):

  try:

    response = requests.head(short_url, allow_redirects=True)

    return response.url

  except Exception as e:

    logging.error(f"Error expanding URL: {e}")

    return None


# Function to convert links to affiliate links using EarnKaro API
# Retry function with exponential backoff
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def convert_to_affiliate_link(url):
    api_url = "https://ekaro-api.affiliaters.in/api/converter/public"
    payload = json.dumps({
        "deal": url,
        "convert_option": "convert_only"
    })
    headers = {
        'Authorization': f'Bearer {EARNKARO_API_TOKEN}',
        'Content-Type': 'application/json'
    }

    try:
        logging.info(f"Converting URL: {url}")
        response = requests.post(api_url, headers=headers, data=payload)

        # Check if request succeeded and return the affiliate link
        response_data = response.json()
        if response.status_code == 200 and response_data.get("success") == 1:
            return response_data.get("data")
        else:
            logging.error(f"Conversion failed: {response_data.get('message')}")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during conversion: {e}")
        raise  # Reraise the error to trigger retry mechanism

    except Exception as e:
        logging.error(f"Unexpected error during conversion: {e}")
        raise  # Reraise the error to trigger retry mechanism




# Function to extract URLs from text

def extract_urls(text):

  return re.findall(r'https?://\S+', text)



@app.on_message(filters.command("start") & filters.private)
async def start(_, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    is_new_user = await log_new_user(user_id, username)
    if is_new_user:
        await app.send_message(LOG_CHANNEL_ID, f"New user started the bot: @{username} (ID: {user_id})")

    text = (
        f"Hello {username}! 🌟\n\n"
        "I'm PriceTrackerBot, your personal assistant for tracking product prices. 💸\n\n"
        "To get started, use the /my_trackings command to start tracking a product."
        "Simply send the URL...\n"
    )
    await message.reply_text(text, quote=True)




@app.on_message(filters.command("help") & filters.private)
async def help(_, message: Message):
    text = (
        "Here are the commands you can use with PriceTrackerBot:\n\n"
        "/start - Start the bot.\n"
        "/my_trackings - List tracked products.\n"
        "/product [ID] - Get details on a product.\n"
        "/stop [ID] - Stop tracking a product.\n"
        "/broadcast - Admin only.\n"
        "/help - Show this message.\n"
    )
    await message.reply_text(text)




async def broadcast(bot, message):
    users = await users_collection.find().to_list(length=None)
    b_msg = message.reply_to_message
    
    total_users = len(users)
    success, failed = 0, 0

    for user in users:
        try:
            await bot.send_message(user["user_id"], b_msg.text.markdown)
            success += 1
        except Exception as e:
            logging.error(f"Failed to send message to {user['user_id']}: {e}")
            failed += 1
        await asyncio.sleep(1)  # Rate limiting to avoid bot API limit

    await message.reply_text(f"Broadcast completed:\nSuccess: {success}\nFailed: {failed}")


@app.on_message(filters.command("my_trackings") & filters.private)
async def track(_, message):
    try:
        chat_id = message.chat.id
        text = await message.reply_text("Fetching Your Products...")
        products = await fetch_all_products(chat_id)  # This queries MongoDB for tracked products.

        if products:
            products_message = "Your Tracked Products:\n\n"
            for i, product in enumerate(products, start=1):
                _id = product.get("product_id")
                product_name = product.get("product_name")
                affiliate_url = product.get("affiliate_url", "#")  # Ensure affiliate links are correctly handled.
                product_price = product.get("price")
                products_message += f"🏷️ **Product {i}**: [{product_name}]({affiliate_url})\n💰 **Current Price**: ₹{product_price}\n❌ Use /stop_{_id} to Stop tracking\n\n"
            await text.edit(products_message, disable_web_page_preview=True)
        else:
            await text.edit("No products added yet")
    except Exception as e:
        logging.error(f"Error fetching products: {e}")



@app.on_message(filters.regex("|".join(all_url_patterns)) | filters.photo | filters.document)
async def track_product_url(_, message: Message):
    try:
        # Ensure the user sends only links, not images or documents
        if message.photo or message.document:
            await message.reply_text("Please send only links, not images or documents.")
            return

        # Extract URLs from the message
        urls = extract_urls(message.text)
        if not urls:
            await message.reply_text("Please send a valid URL.")
            return

        # Send initial status message
        status = await message.reply_text("Analyzing Your Product... Please Wait!!")

        # Loop through each URL
        for url in urls:
            expanded_url = expand_short_url(url) or url

            # Determine platform (Amazon or Flipkart) based on patterns
            platform = "amazon" if any(re.match(pattern, expanded_url) for pattern in amazon_patterns) else "flipkart"

            # Convert to affiliate link using EarnKaro
            affiliate_link = await convert_to_affiliate_link(expanded_url)
            if not affiliate_link:
                await message.reply_text("Failed to convert link to affiliate link.")
                continue

            # Scrape product details (name, price, availability)
            product_name, price, availability, image_url = await scrape(affiliate_link, platform)

            if product_name:
                # Add the new product to the database (check for duplicates by name)
                product_id, is_new_tracking = await add_new_product(message.chat.id, product_name, expanded_url, affiliate_link, price)

                # Conditionally display messages based on whether the product is newly added or already tracked
                if is_new_tracking:
                    product_info = (
                        f"The Product has Started Tracking!  \n\n"
                        f"☀️ {product_name} \n\n"
                        f"Current Price: ₹{price}\n\n"
                        f"[Click here to open in {platform.capitalize()}]({affiliate_link})\n\n"
                        f"⏱ Updated at [ {datetime.datetime.now().strftime('%d %b %Y, %H:%M')} ]"
                    )
                else:
                    product_info = (
                        f"The Product is Already Being Tracked!  \n\n"
                        f"☀️ {product_name} \n\n"
                        f"Current Price: ₹{price}\n\n"
                        f"[Click here to open in {platform.capitalize()}]({affiliate_link})\n\n"
                        f"⏱ Updated at [ {datetime.datetime.now().strftime('%d %b %Y, %H:%M')} ]"
                    )

                # Send product image if available
                if image_url:
                    try:
                        await status.reply_photo(image_url)
                    except Exception as img_error:
                        logging.error(f"Error sending image: {img_error}")
                        await status.reply_text("Failed to send image.")
                await status.edit_text(product_info, disable_web_page_preview=True)
            else:
                await status.edit("Failed to retrieve product details.")
    except Exception as e:
        logging.error(f"Error tracking product URL: {e}")
        await status.edit("An error occurred while processing your request.")

    finally:
        # Delete user's message after processing
        await asyncio.sleep(5)
        await message.delete()




@app.on_message(filters.regex(r"^/product_\w+$") & filters.private)
async def track_product(_, message):
    try:
        # Extract the product tracking ID from the command
        command_parts = message.text.split("_")
        if len(command_parts) != 2 or not command_parts[1]:
            await message.reply_text("Please provide a valid product tracking ID.")
            return
        
        tracking_id = command_parts[1]
        logging.info(f"Fetching product for tracking ID: {tracking_id}")
        
        status = await message.reply_text("Getting Product Info....")

        # Fetch the product from the user's PriceTracker collection using the tracking ID
        user_product = await fetch_one_product(tracking_id)
        logging.info(f"Fetched user product: {user_product}")

        if user_product:
            product_id = user_product.get("product_id")
            logging.info(f"Fetching global product for product ID: {product_id}")

            # Fetch product details from PriceTrackerGlobal using product_id
            global_product = await fetch_global_product(product_id)
            logging.info(f"Fetched global product: {global_product}")

            if global_product:
                # Use affiliate_url instead of the original URL
                affiliate_url = global_product.get("affiliate_url")  # Correct assignment
                product_name = global_product.get("product_name")
                product_price = global_product.get("price")
                maximum_price = global_product.get("upper")
                minimum_price = global_product.get("lower")

                # Format the message
                products_message = (
                    f"🛍 **Product:** [{product_name}]({affiliate_url})\n\n"
                    f"💲 **Current Price:** ₹{product_price}\n"
                    f"📉 **Lowest Price:** ₹{minimum_price}\n"
                    f"📈 **Highest Price:** ₹{maximum_price}\n"
                    f"\n\n\nTo Stop Tracking, use /stop_{tracking_id}"
                )

                await status.edit(products_message, disable_web_page_preview=True)
            else:
                await status.edit("Product not found in global product list.")
        else:
            await status.edit("Product Not Found in your tracking list.")
    except Exception as e:
        logging.error(f"Error retrieving product: {str(e)}")
        await status.edit("Failed to retrieve product details.")




@app.on_message(filters.regex(r"^/stop_\w+$") & filters.private)
async def delete_product(_, message: Message):
    try:
        # Extract the product tracking ID from the command
        command_parts = message.text.split("_")
        if len(command_parts) != 2 or not command_parts[1]:
            await message.reply_text("Please provide a valid product tracking ID.")
            return

        tracking_id = command_parts[1]
        status = await message.reply_text("Deleting Product....")

        # Get the chat ID of the user
        chat_id = message.chat.id

        # Attempt to delete the product from the user's tracking list
        is_deleted = await delete_one(tracking_id, chat_id)
        if is_deleted:
            await status.edit("Product Deleted from Your Tracking List.")
        else:
            await status.edit("Failed to Delete the product from your tracking list.")
    except Exception as e:
        logging.error(f"Error deleting product: {str(e)}")
        await status.edit("Failed to delete the product.")

async def scheduled_check_prices():
    while True:
        await check_prices(app)  # Call `check_prices` periodically.
        await asyncio.sleep(600)  # Check prices every 10 minutes.



def main():
    loop = asyncio.get_event_loop()  # Async event loop for scheduling tasks.
    loop.create_task(scheduled_check_prices())
    app.run()  # Runs the Telegram bot.
    print("Bot Running")



if __name__ == "__main__":

  main()

