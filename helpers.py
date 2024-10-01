#helpers.py

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Database Connection
dbclient = AsyncIOMotorClient(os.getenv("MONGO_URI"))
database = dbclient[os.getenv("DATABASE")]
collection = database[os.getenv("COLLECTION")]
PRODUCTS = database[os.getenv("PRODUCTS")]


# Fetch all products for a specific user
async def fetch_all_products(user_id):
    try:
        cursor = collection.find({"user_id": user_id})
        products = await cursor.to_list(length=None)
        global_products = []

        for product in products:
            global_product = await PRODUCTS.find_one({"_id": product.get("product_id")})
            if global_product:
                global_product["product_id"] = product.get("_id")
                global_products.append(global_product)

        return global_products
    except Exception as e:
        logging.error(f"Error fetching products: {str(e)}")
        return []

# Fetch a specific product by ID

async def fetch_one_product(tracking_id):
    try:
        # Find the product in PriceTracker using the tracking ID
        product = await collection.find_one({"_id": ObjectId(tracking_id)})
        return product if product else None
    except Exception as e:
        logging.error(f"Error fetching product: {str(e)}")
        return None




async def fetch_global_product(product_id):
    try:
        # Find the product in PriceTrackerGlobal using the product_id
        global_product = await PRODUCTS.find_one({"_id": ObjectId(product_id)})
        return global_product if global_product else None
    except Exception as e:
        logging.error(f"Error fetching global product: {str(e)}")
        return None



# Add a new product to the database
# Add a new product to the database with checks for duplicates by product name
async def add_new_product(user_id, product_name, original_url, affiliate_url, initial_price):
    try:
        # Check if the product is already present in pricetrackerglobal by product name
        existing_global_product = await PRODUCTS.find_one({"product_name": product_name})

        if not existing_global_product:
            # If the product does not exist globally, add it to the pricetrackerglobal collection
            global_new_product = {
                "product_name": product_name,
                "url": original_url,  # Store a single URL
                "affiliate_url": affiliate_url,  # Store a single affiliate URL
                "price": initial_price,
                "previous_price": initial_price,
                "upper": initial_price,
                "lower": initial_price,
            }
            insert_result = await PRODUCTS.insert_one(global_new_product)
            new_product_id = insert_result.inserted_id
            logging.info(f"New global product added: {product_name}")
        else:
            # If the product already exists globally, replace the old URL and affiliate link with the new one
            new_product_id = existing_global_product["_id"]

            # Update the product in pricetrackerglobal with the new URL and affiliate link
            await PRODUCTS.update_one(
                {"_id": new_product_id},
                {"$set": {
                    "url": original_url,
                    "affiliate_url": affiliate_url
                }}
            )
            logging.info(f"Global product {product_name} updated with new URL and affiliate link.")

        # Check if the user is already tracking this product
        existing_user_product = await collection.find_one({"user_id": user_id, "product_id": new_product_id})

        if existing_user_product:
            # If the user is already tracking the product, notify them
            logging.info(f"User {user_id} is already tracking the product {product_name}.")
            return existing_user_product["_id"], False  # False indicates it's already being tracked

        # If the user is not tracking the product, create a new link in the user's collection
        new_user_product = {
            "user_id": user_id,
            "product_id": new_product_id,
        }
        result = await collection.insert_one(new_user_product)

        logging.info(f"Product {product_name} added successfully for user {user_id}.")
        return result.inserted_id, True  # True indicates a new tracking was created

    except Exception as e:
        logging.error(f"Error adding product: {str(e)}")
        return None, None


# Update the product price in the database
async def update_product_price(id, new_price):
    try:
        global_product = await PRODUCTS.find_one({"_id": id})
        if global_product:
            upper_price = global_product.get("upper", new_price)
            lower_price = global_product.get("lower", new_price)

            if new_price > upper_price:
                upper_price = new_price
            if new_price < lower_price:
                lower_price = new_price

            # Ensure the database update operation is awaited
            await PRODUCTS.update_one(
                {"_id": id},
                {
                    "$set": {
                        "price": new_price,
                        "upper": upper_price,
                        "lower": lower_price,
                    }
                },
            )
            logging.info(f"Global product prices updated successfully for {id}.")
    except Exception as e:
        logging.error(f"Error updating product price: {str(e)}")
        

async def delete_one(tracking_id, user_id):
    try:
        # Convert tracking_id to ObjectId if necessary
        tracking_object_id = ObjectId(tracking_id)

        # Fetch the product_id before deletion from pricetracker
        user_product = await collection.find_one({"_id": tracking_object_id, "user_id": user_id})

        if not user_product:
            logging.warning(f"Failed to find product {tracking_id} for user {user_id}. Product not found in pricetracker.")
            return False

        # Get the product_id for global product lookup
        product_id = user_product["product_id"]  # This is the _id from pricetrackerglobal

        # Delete the product from pricetracker (user-specific collection)
        result = await collection.delete_one({"_id": tracking_object_id, "user_id": user_id})

        if result.deleted_count > 0:
            logging.info(f"Product {tracking_id} successfully deleted for user {user_id} from pricetracker.")

            # Check if any other users are still tracking the product
            user_tracking = await collection.find_one({"product_id": ObjectId(product_id)})

            # Fetch the product from pricetrackerglobal
            global_product = await PRODUCTS.find_one({"_id": ObjectId(product_id)})

            logging.info(f"Global Product: {global_product}")
            logging.info(f"Users still tracking: {user_tracking}")

            # If no users are tracking it, delete it from pricetrackerglobal
            if not user_tracking and global_product:
                await PRODUCTS.delete_one({"_id": ObjectId(product_id)})
                logging.info(f"Product {product_id} deleted from pricetrackerglobal as no users are tracking it.")

            return True  # Successfully deleted from pricetracker (and possibly pricetrackerglobal)

        else:
            logging.warning(f"Failed to delete product {tracking_id} for user {user_id}. Product not found in pricetracker.")
            return False  # Product was not found in pricetracker

    except Exception as e:
        logging.error(f"Error deleting product {tracking_id} for user {user_id}: {str(e)}")
        return False



