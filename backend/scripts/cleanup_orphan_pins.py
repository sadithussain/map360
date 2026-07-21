"""One-off cleanup for orphan location pins (no successful 3D render).

Pins are now created alongside an image upload and only appear on the map once
TRELLIS produces a ``MapObject``. Before that fix, clicking "Continue to
capture" created a pin immediately, so canceling the capture step left empty
pins in the database. This script removes any pin that has no ``MapObject``
(optionally scoped to groups whose name matches a substring).

Run from the ``backend`` directory with the backend environment active:

    python -m scripts.cleanup_orphan_pins                 # dry run: list only
    python -m scripts.cleanup_orphan_pins --apply         # delete listed pins
    python -m scripts.cleanup_orphan_pins --apply --group "Sadit"

Deletion goes through the ORM so each pin's media submissions cascade-delete.
"""

import argparse
import asyncio

from app.db.database import AsyncSessionLocal, engine
from app.models.group_model import Group
from app.models.location_pin_model import LocationPin
from app.models.map_object_model import MapObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


async def _find_orphan_pins(
    db: AsyncSession,
    group_substring: str | None,
) -> list[tuple[LocationPin, str]]:
    """Return (pin, group_name) for pins that have no map object."""
    has_map_object = (
        select(MapObject.id).where(MapObject.pin_id == LocationPin.id).exists()
    )
    stmt = (
        select(LocationPin, Group.name)
        .join(Group, Group.id == LocationPin.group_id)
        .where(~has_map_object)
        .order_by(Group.name, LocationPin.created_at)
        .options(selectinload(LocationPin.submissions))
    )
    if group_substring:
        stmt = stmt.where(Group.name.ilike(f"%{group_substring}%"))

    result = await db.execute(stmt)
    return list(result.all())


async def main(group_substring: str | None, apply: bool) -> None:
    try:
        async with AsyncSessionLocal() as db:
            rows = await _find_orphan_pins(db, group_substring)

            if not rows:
                print("No orphan pins found.")
                return

            print(f"Found {len(rows)} orphan pin(s) with no 3D render:")
            for pin, group_name in rows:
                print(
                    f"  group={group_name!r} pin={pin.id} "
                    f"osm={pin.osm_building_id} label={pin.label!r} "
                    f"({pin.lat:.5f}, {pin.lng:.5f}) "
                    f"submissions={len(pin.submissions)}"
                )

            if not apply:
                print("\nDry run. Re-run with --apply to delete these pins.")
                return

            for pin, _ in rows:
                await db.delete(pin)
            await db.commit()
            print(f"\nDeleted {len(rows)} orphan pin(s).")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Delete location pins that have no successful 3D render."
    )
    parser.add_argument(
        "--group",
        default=None,
        help="Only pins in groups whose name contains this substring "
        "(case-insensitive).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete the pins. Without this flag the script only "
        "lists what it would delete.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.group, args.apply))
