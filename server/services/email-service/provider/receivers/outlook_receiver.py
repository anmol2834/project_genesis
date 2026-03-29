"""
Outlook Event Receiver
Receives and validates Microsoft Graph webhook notifications.
"""

from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
import hmac
import hashlib

from shared.logger import get_logger
from provider.filters.email_filter import EmailFilter
from provider.deduplicator.event_deduplicator import EventDeduplicator
from normalizer.normalizer import EmailNormalizer
from email_queue.producer.event_producer import EventProducer

logger = get_logger(__name__)


class OutlookReceiver:
    """Handles incoming Outlook Graph webhook notifications."""

    def __init__(self):
        self.email_filter = EmailFilter()
        self.deduplicator = EventDeduplicator()
        self.normalizer = EmailNormalizer()
        self.queue_producer = EventProducer()

    async def receive_notification(self, request: Request) -> Dict[str, Any]:
        """
        Receive and process Outlook webhook notification.
        
        Graph sends:
        {
          "value": [
            {
              "subscriptionId": "subscription-id",
              "clientState": "account-id",
              "changeType": "created",
              "resource": "Users/user-id/Messages/message-id",
              "resourceData": {
                "@odata.type": "#Microsoft.Graph.Message",
                "@odata.id": "Users/user-id/Messages/message-id",
                "id": "message-id"
              }
            }
          ]
        }
        """
        # Handle validation request
        validation_token = request.query_params.get("validationToken")
        if validation_token:
            logger.info("Outlook webhook validation request received")
            return {"validationToken": validation_token}

        try:
            body = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse Outlook notification: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        # Validate client state (optional but recommended)
        # await self._validate_client_state(body)

        notifications = body.get("value", [])
        
        if not notifications:
            logger.warning("Outlook notification has no value array")
            raise HTTPException(status_code=400, detail="No notifications")

        results = []
        
        for notification in notifications:
            subscription_id = notification.get("subscriptionId")
            change_type = notification.get("changeType")
            resource = notification.get("resource")
            client_state = notification.get("clientState")
            
            resource_data = notification.get("resourceData", {})
            message_id = resource_data.get("id")

            if not subscription_id or not message_id:
                logger.warning(f"Outlook notification missing required fields: {notification}")
                continue

            # Only process "created" events (new emails)
            if change_type != "created":
                logger.debug(f"Ignoring Outlook change type: {change_type}")
                continue

            # Deduplicate
            dedup_key = f"outlook_{subscription_id}_{message_id}"
            if await self.deduplicator.is_duplicate(dedup_key):
                logger.debug(f"Duplicate Outlook notification: {message_id}")
                results.append({"status": "duplicate", "message_id": message_id})
                continue

            logger.info(
                f"Outlook notification received: subscription={subscription_id}, "
                f"message={message_id}"
            )

            # Mark as processed
            await self.deduplicator.mark_processed(dedup_key)

            raw_event = {
                "status": "received",
                "provider": "outlook",
                "subscription_id": subscription_id,
                "message_id": message_id,
                "resource": resource,
                "client_state": client_state
            }
            
            # Normalize event
            normalized_event = await self.normalizer.normalize("outlook", raw_event)
            
            if normalized_event:
                # Push to queue
                queued = await self.queue_producer.produce(normalized_event)
                
                results.append({
                    "status": "queued" if queued else "normalized",
                    "message_id": normalized_event.message_id,
                    "user_id": normalized_event.user_id,
                    "queued": queued
                })
            else:
                results.append(raw_event)

        return {"status": "processed", "count": len(results), "results": results}

    async def _validate_client_state(self, body: Dict[str, Any]):
        """Validate clientState matches expected value."""
        # TODO: Implement client state validation
        pass

    def validate_signature(self, request: Request, body: bytes) -> bool:
        """
        Validate Microsoft Graph webhook signature.
        For production, implement signature validation.
        """
        # TODO: Implement signature validation
        # https://docs.microsoft.com/en-us/graph/webhooks#notification-endpoint-validation
        return True
