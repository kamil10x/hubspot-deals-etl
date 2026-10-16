import dlt
import logging
from typing import Dict, List, Any, Iterator, Optional, Callable
# from .api_service import APIService
from .hubspot_api_service import HubSpotAPIService
from loki_logger import get_logger, log_business_event, log_security_event
from datetime import datetime, timezone, date

def transform_hubspot_deal(
    record: Dict[str, Any],
) -> Dict[str, Any]:
    """Flatten and normalize a HubSpot deal record."""
    properties = record.get("properties") or {}

    deal = {
        "id": str(record["id"]),
        **properties,
    }

    # Convert amount to a numeric value.
    amount = deal.get("amount")
    if amount not in (None, ""):
        try:
            deal["amount"] = float(amount)
        except (TypeError, ValueError):
            deal["amount"] = None

    # Normalize HubSpot date fields.
    for field in ("createdate", "closedate", "hs_lastmodifieddate"):
        value = deal.get(field)

        if value in (None, ""):
            continue

        try:
            if isinstance(value, (int, float)) or str(value).isdigit():
                timestamp = float(value) / 1000
                deal[field] = datetime.fromtimestamp(
                    timestamp, tz=timezone.utc
                ).isoformat()
            else:
                parsed = datetime.fromisoformat(
                    str(value).replace("Z", "+00:00")
                )
                deal[field] = parsed.isoformat()
        except (ValueError, TypeError, OverflowError, OSError):
            # Preserve the original value if it cannot be parsed.
            pass

    return deal


def create_data_source(
    job_config: Dict[str, Any],
    auth_config: Dict[str, Any],
    filters: Dict[str, Any],
    checkpoint_callback: Optional[Callable] = None,
    check_cancel_callback: Optional[Callable] = None,
    check_pause_callback: Optional[Callable] = None,  # Add pause callback parameter
    resume_from: Optional[Dict[str, Any]] = None,
):
    """
    Create DLT source function for Hubspot_Deals data extraction with checkpoint support
    """
    logger = get_logger(__name__)
    api_service = HubSpotAPIService(
        access_token=auth_config.get("accessToken")
    )

    access_token = auth_config.get("accessToken")
    if not access_token:
        raise ValueError("No access token found in auth configuration")

    organization_id = job_config.get("organizationId")
    if not organization_id:
        raise ValueError("No organization ID found in job configuration")

    #  To Be Removed Later
    logger.info(
        "Starting Hubspot_Deals data extraction",
        extra={
            "organization_id": organization_id,
            "filters": filters,
            "auth_config": auth_config,
            "job_config": job_config,
        },
    )

    @dlt.resource(
        name="hubspot_deals",
        write_disposition="merge",
        primary_key="id",
    )
    def get_main_data() -> Iterator[Dict[str, Any]]:
        """
        Extract main data from Hubspot_Deals API with checkpoint support
        
        # HubSpot Deals extraction with cursor-based pagination and transformation.
        
        """

        # Initialize state
        if resume_from:
            after = resume_from.get("cursor")
            page_count = resume_from.get("page_number", 0)
            total_records = resume_from.get("records_processed", 0)
            logger.info(
                "Resuming data extraction",
                extra={
                    "operation": "data_extraction",
                    "page_number": page_count + 1,
                    "total_processed": total_records,
                },
            )
        else:
            after = None
            page_count = 0
            total_records = 0
            logger.info(
                "Starting fresh data extraction",
                extra={"operation": "data_extraction", "source": "hubspot_deals"},
            )

        # Configuration
        checkpoint_interval = 10
        cancel_check_interval = 1
        pause_check_interval = 1  # Check for pause more frequently than cancel
        job_id = filters.get("scan_id", "unknown")

        while page_count < 1000:  # Safety limit
            try:
                # Check for cancellation
                if page_count % cancel_check_interval == 0:
                    if check_cancel_callback and check_cancel_callback(job_id):
                        logger.info(
                            "Extraction cancelled by user",
                            extra={
                                "operation": "data_extraction",
                                "job_id": job_id,
                                "page_number": page_count + 1,
                                "total_processed": total_records,
                            },
                        )

                        # Save cancellation checkpoint
                        if checkpoint_callback:
                            try:
                                cancel_checkpoint = {
                                    "phase": "main_data_cancelled",
                                    "records_processed": total_records,
                                    "cursor": after,
                                    "page_number": page_count,
                                    "batch_size": 100,
                                    "checkpoint_data": {
                                        "cancellation_reason": "user_requested",
                                        "cancelled_at_page": page_count,
                                        "service": "hubspot_deals",
                                    },
                                }
                                checkpoint_callback(job_id, cancel_checkpoint)
                            except Exception as e:
                                logger.warning(
                                    "Failed to save cancellation checkpoint",
                                    extra={"job_id": job_id, "error": str(e)},
                                )
                        break

                # Check for pause request
                if page_count % pause_check_interval == 0:
                    if check_pause_callback and check_pause_callback(job_id):
                        logger.info(
                            "Extraction paused by user",
                            extra={
                                "operation": "data_extraction",
                                "job_id": job_id,
                                "page_number": page_count + 1,
                                "total_processed": total_records,
                            },
                        )

                        # Save pause checkpoint - this allows resuming from exact position
                        if checkpoint_callback:
                            try:
                                pause_checkpoint = {
                                    "phase": "main_data_paused",
                                    "records_processed": total_records,
                                    "cursor": after,
                                    "page_number": page_count,
                                    "batch_size": 1,
                                    "checkpoint_data": {
                                        "pause_reason": "user_requested",
                                        "paused_at_page": page_count,
                                        "paused_at": datetime.now(
                                            timezone.utc
                                        ).isoformat(),
                                        "service": "hubspot_deals",
                                    },
                                }
                                checkpoint_callback(job_id, pause_checkpoint)

                                logger.info(
                                    "Pause checkpoint saved",
                                    extra={
                                        "operation": "data_extraction",
                                        "job_id": job_id,
                                        "page_number": page_count,
                                        "total_processed": total_records,
                                    },
                                )
                            except Exception as e:
                                logger.warning(
                                    "Failed to save pause checkpoint",
                                    extra={"job_id": job_id, "error": str(e)},
                                )

                        # Exit gracefully - this allows the job to be resumed later
                        break

                logger.debug(
                    "Fetching data page",
                    extra={
                        "operation": "data_extraction",
                        "job_id": job_id,
                        "page_number": page_count + 1,
                    },
                )

                # TODO: Replace with appropriate Hubspot_Deals API call - Done
                # Process HubSpot Deals API response.
                data = api_service.get_deals_page(
                    limit=100,
                    after=after,
                    properties=filters.get(
                        "properties",
                        [
                            "dealname",
                            "amount",
                            "dealstage",
                            "pipeline",
                            "closedate",
                            "createdate",
                            "hs_lastmodifieddate",
                        ],
                    ),
                )

                page_records = 0

                # TODO: Update data processing based on Hubspot_Deals response structure - Done
                # Determine the cursor for the next checkpoint.
                data_key = "results"  # Update based on API response
                if data_key in data and data[data_key]:
                    for record in data[data_key]:
                        # Check for pause/cancel even within record processing for faster response
                        if check_pause_callback and check_pause_callback(job_id):
                            logger.info(
                                "Extraction paused mid-page",
                                extra={
                                    "operation": "data_extraction",
                                    "job_id": job_id,
                                    "page_number": page_count + 1,
                                    "records_in_page": page_records,
                                    "total_processed": total_records + page_records,
                                },
                            )

                            # Save mid-page pause checkpoint
                            if checkpoint_callback:
                                try:
                                    mid_page_checkpoint = {
                                        "phase": "main_data_paused_mid_page",
                                        "records_processed": total_records
                                        + page_records,
                                        "cursor": after,
                                        "page_number": page_count,
                                        "batch_size": 100,
                                        "checkpoint_data": {
                                            "pause_reason": "user_requested_mid_page",
                                            "paused_at_page": page_count,
                                            "records_completed_in_page": page_records,
                                            "paused_at": datetime.now(
                                                timezone.utc
                                            ).isoformat(),
                                            "service": "hubspot_deals",
                                        },
                                    }
                                    
                                    # mid_page_checkpoint = {
                                    #     "phase": "main_data_paused_mid_page",
                                    #     "records_processed": total_records + page_records,
                                    #     "cursor": after,
                                    #     "page_number": page_count,
                                    #     "batch_size": 100,
                                    #     "checkpoint_data": {
                                    #         "pause_reason": "user_requested_mid_page",
                                    #         "paused_at_page": page_count,
                                    #         "records_completed_in_page": page_records,
                                    #         "paused_at": datetime.now(timezone.utc).isoformat(),
                                    #         "service": "hubspot_deals",
                                    #     },
                                    # }

                                    checkpoint_callback(job_id, mid_page_checkpoint)
                                except Exception as e:
                                    logger.warning(
                                        "Failed to save mid-page pause checkpoint",
                                        extra={"job_id": job_id, "error": str(e)},
                                    )
                            return  # Exit the generator

                        # Filter properties if specified
                        #
                        # Transform the HubSpot deal.
                        filtered_record = transform_hubspot_deal(record)

                        # Apply requested property filtering while retaining the ID.
                        requested_properties = filters.get("properties")
                        if requested_properties:
                            allowed_fields = set(requested_properties) | {"id"}
                            filtered_record = {
                                key: value
                                for key, value in filtered_record.items()
                                if key in allowed_fields
                            }

                        # Add extraction metadata.
                        filtered_record.update({
                            "_extracted_at": datetime.now(timezone.utc).isoformat(),
                            "_scan_id": filters.get("scan_id", "unknown"),
                            "_organization_id": (
                                job_config.get("organizationId")
                                or filters.get("organization_id", "unknown")
                            ),
                            "_page_number": page_count + 1,
                            "_source_service": "hubspot_deals",
                        })

                        yield filtered_record
                        page_records += 1

                        #

                # Update counters
                total_records += page_records
                page_count += 1

                # Save checkpoint periodically
                if checkpoint_callback and page_count % checkpoint_interval == 0:
                    try:
                        # TODO: Update pagination logic based on Hubspot_Deals API - Done
                        # Determine the cursor for the next checkpoint.
                        next_cursor = None
                        if (
                            data.get("paging")
                            and data["paging"].get("next")
                            and data["paging"]["next"].get("after")
                        ):
                            next_cursor = data["paging"]["next"]["after"]

                        checkpoint_data = {
                            "phase": "main_data",
                            "records_processed": total_records,
                            "cursor": next_cursor,
                            "page_number": page_count,
                            "batch_size": 100,
                            "checkpoint_data": {
                                "pages_processed": page_count,
                                "last_page_records": page_records,
                                "service": "hubspot_deals",
                            },
                        }

                        checkpoint_callback(job_id, checkpoint_data)

                        logger.debug(
                            "Checkpoint saved",
                            extra={
                                "operation": "data_extraction",
                                "job_id": job_id,
                                "page_number": page_count,
                                "total_records": total_records,
                            },
                        )

                    except Exception as checkpoint_error:
                        logger.warning(
                            "Failed to save checkpoint",
                            extra={
                                "operation": "data_extraction",
                                "job_id": job_id,
                                "error": str(checkpoint_error),
                            },
                        )

                # TODO: Handle pagination based on Hubspot_Deals API response - Done
                # Continue with the next HubSpot page or complete extraction.
                if (
                    data.get("paging")
                    and data["paging"].get("next")
                    and data["paging"]["next"].get("after")
                ):
                    after = data["paging"]["next"]["after"]
                elif data.get("has_more"):
                    after = data.get("next_cursor")
                elif data.get("next_page_token"):
                    after = data.get("next_page_token")
                else:
                    # Final checkpoint on completion
                    if checkpoint_callback:
                        try:
                            final_checkpoint = {
                                "phase": "main_data_completed",
                                "records_processed": total_records,
                                "cursor": None,
                                "page_number": page_count,
                                "batch_size": 100,
                                "checkpoint_data": {
                                    "completion_status": "success",
                                    "total_pages": page_count,
                                    "final_total": total_records,
                                    "service": "hubspot_deals",
                                },
                            }
                            checkpoint_callback(job_id, final_checkpoint)
                        except Exception as e:
                            logger.warning(
                                "Failed to save final checkpoint",
                                extra={"job_id": job_id, "error": str(e)},
                            )

                    logger.info(
                        "Data extraction completed",
                        extra={
                            "operation": "data_extraction",
                            "job_id": job_id,
                            "total_records": total_records,
                            "total_pages": page_count,
                        },
                    )
                    break

            except Exception as e:
                logger.error(
                    "Error fetching data page",
                    extra={
                        "operation": "data_extraction",
                        "job_id": job_id,
                        "page_number": page_count + 1,
                        "error": str(e),
                    },
                    exc_info=True,
                )

                # Save error checkpoint for debugging
                if checkpoint_callback:
                    try:
                        error_checkpoint = {
                            "phase": "main_data_error",
                            "records_processed": total_records,
                            "cursor": after,
                            "page_number": page_count,
                            "batch_size": 100,
                            "checkpoint_data": {
                                "error": str(e),
                                "error_page": page_count + 1,
                                "recovery_cursor": after,
                                "service": "hubspot_deals",
                            },
                        }
                        checkpoint_callback(job_id, error_checkpoint)
                    except:
                        pass

                raise e

    return [get_main_data]