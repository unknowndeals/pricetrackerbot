#scraper.py

from amazon import track_prices
from python_flipkart_scraper import ExtractFlipkart
import logging
async def scrape(url, platform):
    if platform == "amazon":
        # Scrape Amazon product details
        price, product_name, availability, images = await track_prices(url)
        
        # If the product is unavailable on Amazon, set price to 0
        if not availability:
            price = 0  # Use 0 as placeholder for unavailable products

        logging.info(f"Amazon Product: {product_name}, Price: {price}, Availability: {availability}")
        
        return product_name, price, availability, images[0] if images else None
    
    elif platform == "flipkart":
        # Scrape Flipkart product details
        product = ExtractFlipkart(url)
        product_name = product.get_title()
        price = product.get_price() if product.is_available() else 0  # Set price to 0 if unavailable
        availability = "In Stock" if product.is_available() else "Out of Stock"
        images = product.get_images()

        logging.info(f"Flipkart Product: {product_name}, Price: {price}, Availability: {availability}")

        return product_name, price, availability, images[0] if images else None
    
    else:
        raise ValueError("Unsupported platform")
