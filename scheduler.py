# scheduler.py

import time
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from scraper import scrape
from dotenv import load_dotenv
import logging
from helpers import fetch_all_products

load_dotenv()

# Database Connection
dbclient = AsyncIOMotorClient(os.getenv("MONGO_URI"))
database = dbclient[os.getenv("DATABASE")]
PRODUCTS = database[os.getenv("PRODUCTS")]

async def check_prices(app):
    """Check the prices of products and update if changed."""
    print("Checking Prices for Products...")
    changed_products = []

    async for product in PRODUCTS.find():
        try:
            platform = "amazon" if "amazon" in product["url"] else "flipkart"
            product_name, current_price, availability, image_url = await scrape(product["url"], platform)

            if current_price != product["price"]:
                await update_product_in_db(product, current_price)
                changed_products.append(product["_id"])
        except Exception as e:
            logging.error(f"Error scraping product {product['url']}: {e}")
        await asyncio.sleep(1)

    print("Completed")
    await notify_users(changed_products, app)

async def update_product_in_db(product, current_price):
    """Update product details in the database."""
    await PRODUCTS.update_one(
        {"_id": product["_id"]},
        {
            "$set": {
                "price": current_price,
                "previous_price": product["price"],
                "lower": min(current_price, product["lower"]),
                "upper": max(current_price, product["upper"]),
            }
        },
    )

async def notify_users(changed_products, app):
    """Notify users of price changes."""
    for changed_product in changed_products:
        global_product = await PRODUCTS.find_one({"_id": changed_product})
        if global_product:
            price_change, change_type = calculate_price_change(global_product)

            # Notify the user if there is a price change
            if price_change > 0:
                if change_type == "increased":
                    message = (
                        f"🚨 The price of **{global_product['product_name']}** has **increased** by ₹{price_change}.\n"
                        f"   - Previous Price: ₹{global_product['previous_price']}\n"
                        f"   - Current Price: ₹{global_product['price']}\n"
                        f"   - [Check it out here]({global_product['affiliate_url']})"
                    )
                elif change_type == "decreased":
                    message = (
                        f"🎉 The price of **{global_product['product_name']}** has **decreased** by ₹{price_change}.\n"
                        f"   - Previous Price: ₹{global_product['previous_price']}\n"
                        f"   - Current Price: ₹{global_product['price']}\n"
                        f"   - [Check it out here]({global_product['affiliate_url']})"
                    )

                user_products = await fetch_all_products(global_product["_id"])
                for user in user_products:
                    await app.send_message(chat_id=user["user_id"], text=message, disable_web_page_preview=True)

def calculate_price_change(product):
    """Calculate the absolute price change and determine if the price increased or decreased."""
    try:
        # Convert price and previous_price to floats for arithmetic operation
        current_price = float(product["price"])
        previous_price = float(product["previous_price"])

        # Calculate the absolute change
        price_difference = current_price - previous_price

        # Determine if price increased or decreased
        if price_difference > 0:
            return abs(price_difference), "increased"
        elif price_difference < 0:
            return abs(price_difference), "decreased"
        else:
            return 0, "no change"  # No change in price

    except (ValueError, TypeError) as e:
        logging.error(f"Error calculating price change: {e}") 
        return 0, "error"


async def compare_prices():
    """Compare current and previous prices of products."""
    print("Comparing Prices...")
    product_with_changes = []
    async for product in PRODUCTS.find():
        current_price = product.get("price")
        previous_price = product.get("previous_price")
        if current_price != previous_price:
            product_with_changes.append(product.get("_id"))
    return product_with_changes
