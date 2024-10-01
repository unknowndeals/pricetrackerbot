#amazon.py

from python_amazon_scraper import ExtractAmazon
import logging
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

# Custom exception definitions
class NetworkError(Exception):
    pass

class ParsingError(Exception):
    pass


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def track_prices(url):
    try:
        product = ExtractAmazon(url)
        product_name = product.get_title()
        price = product.get_price()
        is_available = product.is_available()
        images = product.get_images()

        logging.info(f"Product Images = {images}")
        image_url = images if images else None
        return price, product_name, is_available, image_url

    except NetworkError as e:
        logging.error(f"Network error while scraping Amazon: {e}")
        raise  # Reraise to retry on network failure
    except ParsingError as e:
        logging.error(f"Error parsing product details: {e}")
        raise  # Retry on parsing errors
    except Exception as e:
        logging.error(f"Unknown error scraping product from Amazon: {e}")
        raise  # Reraise for unknown errors to trigger retry
