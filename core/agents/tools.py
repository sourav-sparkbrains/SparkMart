import logging
import uuid
import hashlib
from langchain.tools import tool
from sqlalchemy import text

from db.database import engine

logger = logging.getLogger(__name__)


def get_next_user_id():
    """
    Get the next available user_id:
    - First tries to find an available 2-digit number (10-99)
    - If all 2-digit numbers are taken, moves to 3-digit (100+)
    """
    try:
        with engine.connect() as conn:
            query = text("SELECT user_id FROM orders WHERE user_id IS NOT NULL")
            result = conn.execute(query)
            existing_ids = set(row[0] for row in result.fetchall())

            logger.info(f"Existing user_ids: {existing_ids}")

            for num in range(10, 100):
                if num not in existing_ids:
                    logger.info(f"Found available 2-digit user_id: {num}")
                    return num
            next_id = 100
            while next_id in existing_ids:
                next_id += 1

            logger.info(f"All 2-digit IDs taken, using 3-digit user_id: {next_id}")
            return next_id

    except Exception as e:
        logger.error(f"Error getting next user_id: {e}")
        return 10


@tool("save_order_tool")
def save_order_tool(order_details: dict):
    """
    - Creates new orders (normal purchase)
    - Updates existing orders with complaint details (file + text)
    Input dict may contain:
        product_name: str (required for new orders)
        session_id: int (required for new orders)
        order_id: str (optional for purchase; REQUIRED for complaint update)
        complaint_text: str (optional)
        complaint_file_url: str (optional)
    """

    product_name = order_details.get("product_name")
    user_id = get_next_user_id()
    order_id = order_details.get("order_id")
    complaint_text = order_details.get("complaint_text")
    complaint_file_url = order_details.get("complaint_file_url")


    logger.info(f"save_order_tool called with:")
    logger.info(f"user_id: {user_id}")
    logger.info(f"order_id: {order_id}")
    logger.info(f"complaint_text: {complaint_text}")
    logger.info(f"complaint_file_url: {complaint_file_url}")

    if order_id and (complaint_text or complaint_file_url):
        try:
            with engine.connect() as conn:
                check_query = text("""
                    SELECT complaint_file_url FROM orders 
                    WHERE order_id = :order_id
                """)
                result = conn.execute(check_query, {"order_id": order_id})
                row = result.fetchone()

                existing_urls = None
                if row and row[0]:
                    existing_urls = row[0]

                final_url = complaint_file_url
                if complaint_file_url and existing_urls:
                    final_url = f"{existing_urls};{complaint_file_url}"
                elif not complaint_file_url and existing_urls:
                    final_url = existing_urls

                update_query = text("""
                    UPDATE orders
                    SET 
                        is_complaint = 1,
                        complaint_text = COALESCE(:complaint_text, complaint_text),
                        complaint_file_url = :complaint_file_url
                    WHERE order_id = :order_id
                """)

                conn.execute(update_query, {
                    "complaint_text": complaint_text,
                    "complaint_file_url": final_url,
                    "order_id": order_id
                })
                conn.commit()

            file_msg = " with attached evidence" if complaint_file_url else ""
            return f"Complaint recorded for Order `{order_id}`{file_msg}. Our team will review your issue and respond within 24 hours."

        except Exception as e:
            logger.error(f"Database Error (complaint update): {e}")
            return f"I apologize, but I encountered an error saving your complaint. Please try again or contact support directly."

    if not product_name:
        return "Error: product_name is required for order placement."

    generated_order_id = f"order_{uuid.uuid4().hex[:10]}"
    logger.info(f"generated_order_id {generated_order_id}")
    try:
        with engine.connect() as conn:
            insert_query = text("""
                INSERT INTO orders (order_id, product_name,user_id)
                VALUES (:order_id, :product_name, :user_id)
            """)

            conn.execute(insert_query, {
                "order_id": generated_order_id,
                "product_name": product_name,
                "user_id": user_id
            })
            conn.commit()

        return (
            f"Your order for **{product_name}** has been placed successfully!\n"
            f"Your Order ID: `{generated_order_id}` and User Id: `{user_id}`\n"
            "Please save this IDs for future reference."
        )

    except Exception as e:
        logger.error(f"Database Error (order placement): {e}")
        return f"I apologize, but I encountered an error placing your order. Please try again."