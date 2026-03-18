"""cli entry points for background jobs"""
import argparse
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("spotme.cli")


def whoop_sync():
    """sync whoop biometrics with dedup and auth error tracking"""
    from server.database import SessionLocal
    from server.models import WhoopData, SystemMemory
    from server.config import settings

    db = SessionLocal()
    try:
        # dedup: skip if last sync was less than 3 hours ago
        latest = db.query(WhoopData).order_by(WhoopData.synced_at.desc()).first()
        if latest and latest.synced_at:
            from datetime import datetime, timedelta
            age = datetime.utcnow() - latest.synced_at
            if age < timedelta(hours=3):
                logger.info("skipping sync — last sync was %s ago", age)
                return

        if not settings.whoop_access_token:
            logger.warning("whoop not configured — no access token")
            return

        try:
            from server.services.whoop_service import create_whoop_client, sync_whoop_biometrics
            client = create_whoop_client()
            result = asyncio.run(sync_whoop_biometrics(db, client))
            logger.info("whoop sync result: %s", result)

            # clear auth failure flag on success
            status = db.query(SystemMemory).filter_by(key="whoop_status").first()
            if status:
                db.delete(status)
                db.commit()

        except Exception as e:
            error_str = str(e)
            logger.error("whoop sync failed: %s", error_str)

            # track consecutive auth failures
            if "401" in error_str or "403" in error_str or "unauthorized" in error_str.lower():
                import json
                status = db.query(SystemMemory).filter_by(key="whoop_status").first()
                failures = 1
                if status:
                    try:
                        data = json.loads(status.content)
                        failures = data.get("consecutive_failures", 0) + 1
                    except (json.JSONDecodeError, AttributeError):
                        failures = 1
                    status.content = json.dumps({"auth_failed": failures >= 3, "consecutive_failures": failures})
                else:
                    db.add(SystemMemory(key="whoop_status", content=json.dumps({"auth_failed": False, "consecutive_failures": 1})))
                db.commit()
                logger.warning("whoop auth failure #%d", failures)

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(prog="spotme-cli")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("whoop_sync", help="sync whoop biometrics")
    args = parser.parse_args()
    if args.command == "whoop_sync":
        whoop_sync()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
